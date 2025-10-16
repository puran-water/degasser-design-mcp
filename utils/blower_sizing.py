"""
Blower Sizing and Power Calculations

Uses validated functions from fluids.compressible module for accurate
isothermal, polytropic, and adiabatic power calculations for air blowers
in packed tower air strippers.

Reference:
- Perry's Chemical Engineers' Handbook 8th Ed, Section 10
- CalebBell/fluids library compressible module
- GPSA Engineering Data Book, Section 13
"""

import logging
from typing import Dict, Optional
import math

try:
    from fluids.compressible import (
        isothermal_work_compression,
        isentropic_work_compression,
        isentropic_T_rise_compression,
        polytropic_exponent
    )
    from fluids.constants import R as R_UNIVERSAL  # J/(mol·K)
    from fluids.atmosphere import M0  # kg/kmol - molecular weight of air
except ImportError as e:
    raise ImportError(
        "fluids library is required for blower sizing calculations. "
        "Install with: pip install fluids"
    ) from e

logger = logging.getLogger(__name__)

# Gas constants derived from fluids library
M_AIR = M0 / 1000.0  # kg/mol - molecular weight of air (convert from kg/kmol)
R_AIR = R_UNIVERSAL / M_AIR  # J/(kg·K) - specific gas constant for air
GAMMA_AIR = 1.4  # Ratio of specific heats for air (Cp/Cv)


def select_blower_type(
    compression_ratio: float,
    user_override: Optional[str] = None
) -> Dict[str, any]:
    """
    Select blower type based on compression ratio.

    Args:
        compression_ratio: β = P_discharge / P_inlet
        user_override: Optional user-specified blower type

    Returns:
        Dict with blower_type, thermodynamic_model, and default_efficiency
    """

    if user_override:
        # User override - map to correct thermodynamic model
        # Normalize user input to handle aliases like "Rotary Lobe (Roots)"
        normalized_override = user_override.replace(" (Roots)", "").replace(" (roots)", "")

        override_mapping = {
            "Multistage Centrifugal": {
                'blower_type': user_override,  # Use original name in output
                'thermodynamic_model': 'Isothermal',
                'default_efficiency': 0.70
            },
            "Rotary Lobe": {
                'blower_type': user_override,  # Use original name in output
                'thermodynamic_model': 'Polytropic',
                'default_efficiency': 0.65
            },
            "Single-Stage Compressor": {
                'blower_type': user_override,  # Use original name in output
                'thermodynamic_model': 'Adiabatic',
                'default_efficiency': 0.75
            },
            "Positive Displacement": {
                'blower_type': user_override,  # Use original name in output
                'thermodynamic_model': 'Polytropic',
                'default_efficiency': 0.65
            }
        }

        if normalized_override in override_mapping:
            logger.info(f"Using user-specified blower type: {user_override}")
            return override_mapping[normalized_override]
        else:
            logger.warning(f"Invalid blower type override: {user_override}. Using automatic selection.")

    # Automatic selection based on compression ratio
    if compression_ratio <= 1.2:  # ≤ 3 psig
        return {
            'blower_type': 'Multistage Centrifugal',
            'thermodynamic_model': 'Isothermal',
            'default_efficiency': 0.70  # 0.65-0.80 range
        }
    elif compression_ratio <= 1.5:  # 3-7 psig
        return {
            'blower_type': 'Rotary Lobe (Roots)',
            'thermodynamic_model': 'Polytropic',
            'default_efficiency': 0.65  # 0.60-0.70 range
        }
    else:  # > 7 psig
        return {
            'blower_type': 'Single-Stage Compressor',
            'thermodynamic_model': 'Adiabatic',
            'default_efficiency': 0.75  # 0.70-0.85 range
        }


def calculate_isothermal_power(
    volumetric_flow_m3_s: float,
    inlet_pressure_pa: float,
    discharge_pressure_pa: float,
    inlet_temperature_k: float,
    blower_efficiency: float = 0.70
) -> float:
    """
    Calculate isothermal compression power using fluids library.

    Suitable for compression ratio β ≤ 1.2 (low pressure applications).

    Args:
        volumetric_flow_m3_s: Volumetric flow rate at inlet, m³/s
        inlet_pressure_pa: Inlet pressure, Pa
        discharge_pressure_pa: Discharge pressure, Pa
        inlet_temperature_k: Inlet temperature, K
        blower_efficiency: Blower isentropic efficiency (0-1)

    Returns:
        Shaft power required, kW
    """
    compression_ratio = discharge_pressure_pa / inlet_pressure_pa

    # Use fluids library - returns J/mol
    work_per_mol_j = isothermal_work_compression(
        P1=inlet_pressure_pa,
        P2=discharge_pressure_pa,
        T=inlet_temperature_k,
        Z=1.0  # Assume ideal gas for air at low pressure
    )

    # Convert to total power: J/mol → W
    # molar_flow = volumetric_flow * density / molecular_weight
    # But easier: W = (J/mol) * (mol/s) = (J/mol) * (P*V)/(R*T)
    molar_flow_mol_s = (inlet_pressure_pa * volumetric_flow_m3_s) / (R_UNIVERSAL * inlet_temperature_k)
    ideal_power_w = work_per_mol_j * molar_flow_mol_s

    # Account for efficiency
    shaft_power_w = ideal_power_w / blower_efficiency
    shaft_power_kw = shaft_power_w / 1000.0

    logger.debug(
        f"Isothermal: β={compression_ratio:.3f}, "
        f"W_shaft={shaft_power_kw:.2f} kW (η={blower_efficiency:.2f})"
    )

    return shaft_power_kw


def calculate_polytropic_power(
    volumetric_flow_m3_s: float,
    inlet_pressure_pa: float,
    discharge_pressure_pa: float,
    inlet_temperature_k: float = 298.15,
    polytropic_efficiency: float = 0.65
) -> Dict[str, float]:
    """
    Calculate polytropic compression power using fluids library.

    Suitable for compression ratio 1.2 < β ≤ 1.5 (medium pressure applications).
    Derives proper polytropic exponent n from efficiency instead of using γ=1.4.

    Args:
        volumetric_flow_m3_s: Volumetric flow rate at inlet, m³/s
        inlet_pressure_pa: Inlet pressure, Pa
        discharge_pressure_pa: Discharge pressure, Pa
        inlet_temperature_k: Inlet temperature, K
        polytropic_efficiency: Polytropic efficiency (0-1), typically 0.60-0.70 for rotary lobe

    Returns:
        Dict with shaft_power_kw and discharge_temperature_c
    """
    compression_ratio = discharge_pressure_pa / inlet_pressure_pa

    # Derive polytropic exponent n from efficiency
    # Using fluids.compressible.polytropic_exponent
    n = polytropic_exponent(k=GAMMA_AIR, eta_p=polytropic_efficiency)

    # Calculate work using isentropic_work_compression with polytropic exponent
    # Returns J/mol
    work_per_mol_j = isentropic_work_compression(
        T1=inlet_temperature_k,
        k=n,  # Use polytropic exponent n, not γ
        Z=1.0,
        P1=inlet_pressure_pa,
        P2=discharge_pressure_pa,
        eta=polytropic_efficiency
    )

    # Convert to total power
    molar_flow_mol_s = (inlet_pressure_pa * volumetric_flow_m3_s) / (R_UNIVERSAL * inlet_temperature_k)
    shaft_power_w = work_per_mol_j * molar_flow_mol_s
    shaft_power_kw = shaft_power_w / 1000.0

    # Calculate discharge temperature using isentropic_T_rise_compression
    discharge_temperature_k = isentropic_T_rise_compression(
        T1=inlet_temperature_k,
        P1=inlet_pressure_pa,
        P2=discharge_pressure_pa,
        k=n,  # Use polytropic exponent n
        eta=polytropic_efficiency
    )
    discharge_temperature_c = discharge_temperature_k - 273.15

    logger.debug(
        f"Polytropic: β={compression_ratio:.3f}, n={n:.3f} (from η_p={polytropic_efficiency:.2f}), "
        f"W_shaft={shaft_power_kw:.2f} kW, T2={discharge_temperature_c:.1f}°C"
    )

    return {
        'shaft_power_kw': shaft_power_kw,
        'discharge_temperature_c': discharge_temperature_c
    }


def calculate_adiabatic_power(
    volumetric_flow_m3_s: float,
    inlet_pressure_pa: float,
    discharge_pressure_pa: float,
    inlet_temperature_k: float = 298.15,
    gamma: float = 1.4,
    isentropic_efficiency: float = 0.75
) -> Dict[str, float]:
    """
    Calculate adiabatic/isentropic compression power.

    Suitable for compression ratio β > 1.5 (high pressure applications).
    Includes discharge temperature and aftercooling heat duty.

    Args:
        volumetric_flow_m3_s: Volumetric flow rate at inlet, m³/s
        inlet_pressure_pa: Inlet pressure, Pa
        discharge_pressure_pa: Discharge pressure, Pa
        inlet_temperature_k: Inlet temperature, K
        gamma: Ratio of specific heats (1.4 for air)
        isentropic_efficiency: Isentropic efficiency (0-1)

    Returns:
        Dict with shaft_power_kw, discharge_temperature_k, and aftercooling_heat_duty_kw
    """

    compression_ratio = discharge_pressure_pa / inlet_pressure_pa

    # Adiabatic/isentropic work: W = (γ/(γ-1))·P1·Q·[(P2/P1)^((γ-1)/γ) - 1]
    exponent = (gamma - 1.0) / gamma
    isentropic_work_w = (
        (gamma / (gamma - 1.0)) *
        inlet_pressure_pa *
        volumetric_flow_m3_s *
        (math.pow(compression_ratio, exponent) - 1.0)
    )

    # Shaft power accounting for efficiency
    shaft_power_w = isentropic_work_w / isentropic_efficiency

    shaft_power_kw = shaft_power_w / 1000.0

    # Calculate discharge temperature
    # T2_isentropic = T1·(P2/P1)^((γ-1)/γ)
    T2_isentropic = inlet_temperature_k * math.pow(compression_ratio, exponent)

    # Actual discharge temperature accounting for efficiency
    # T2_actual = T1 + (T2_isentropic - T1) / η_isentropic
    T2_actual = inlet_temperature_k + (T2_isentropic - inlet_temperature_k) / isentropic_efficiency

    # Aftercooling heat duty (cool back to inlet temperature)
    # Q = m·cp·ΔT, where m = ρ·V
    # For ideal gas: ρ = P/(R·T)
    gas_density_kg_m3 = inlet_pressure_pa / (R_AIR * inlet_temperature_k)
    mass_flow_kg_s = gas_density_kg_m3 * volumetric_flow_m3_s
    cp_air = 1005.0  # J/(kg·K) at 25°C

    aftercooling_heat_duty_w = mass_flow_kg_s * cp_air * (T2_actual - inlet_temperature_k)
    aftercooling_heat_duty_kw = aftercooling_heat_duty_w / 1000.0

    logger.debug(
        f"Adiabatic: β={compression_ratio:.3f}, γ={gamma:.2f}, "
        f"W_shaft={shaft_power_kw:.2f} kW, "
        f"T2={T2_actual:.1f} K, Q_cool={aftercooling_heat_duty_kw:.2f} kW "
        f"(η={isentropic_efficiency:.2f})"
    )

    return {
        'shaft_power_kw': shaft_power_kw,
        'discharge_temperature_k': T2_actual,
        'discharge_temperature_c': T2_actual - 273.15,
        'aftercooling_heat_duty_kw': aftercooling_heat_duty_kw
    }


def calculate_blower_power(
    air_flow_rate_m3_h: float,
    total_pressure_drop_pa: float,
    inlet_pressure_pa: float = 101325.0,
    inlet_temperature_c: float = 25.0,
    blower_efficiency_override: Optional[float] = None,
    motor_efficiency: float = 0.92,
    blower_type_override: Optional[str] = None
) -> Dict[str, any]:
    """
    Calculate blower power requirements with automatic type selection.

    Args:
        air_flow_rate_m3_h: Volumetric air flow rate, m³/h
        total_pressure_drop_pa: Total system pressure drop, Pa
        inlet_pressure_pa: Inlet pressure (atmospheric), Pa
        inlet_temperature_c: Inlet temperature, °C
        blower_efficiency_override: Override default blower efficiency
        motor_efficiency: Electric motor efficiency (0-1)
        blower_type_override: Override automatic blower type selection

    Returns:
        Dict with complete blower specifications and power calculations
    """

    # Convert flow rate to m³/s
    volumetric_flow_m3_s = air_flow_rate_m3_h / 3600.0

    # Calculate discharge pressure
    discharge_pressure_pa = inlet_pressure_pa + total_pressure_drop_pa

    # Calculate compression ratio
    compression_ratio = discharge_pressure_pa / inlet_pressure_pa

    # Select blower type and thermodynamic model
    blower_selection = select_blower_type(
        compression_ratio=compression_ratio,
        user_override=blower_type_override
    )

    blower_type = blower_selection['blower_type']
    thermodynamic_model = blower_selection['thermodynamic_model']
    blower_efficiency = blower_efficiency_override or blower_selection['default_efficiency']

    # Convert temperature to Kelvin
    inlet_temperature_k = inlet_temperature_c + 273.15

    # Calculate shaft power based on thermodynamic model
    if thermodynamic_model == 'Isothermal':
        shaft_power_kw = calculate_isothermal_power(
            volumetric_flow_m3_s=volumetric_flow_m3_s,
            inlet_pressure_pa=inlet_pressure_pa,
            discharge_pressure_pa=discharge_pressure_pa,
            inlet_temperature_k=inlet_temperature_k,
            blower_efficiency=blower_efficiency
        )
        discharge_temperature_c = inlet_temperature_c  # Isothermal assumption
        aftercooling_heat_duty_kw = 0.0

    elif thermodynamic_model == 'Polytropic':
        polytropic_result = calculate_polytropic_power(
            volumetric_flow_m3_s=volumetric_flow_m3_s,
            inlet_pressure_pa=inlet_pressure_pa,
            discharge_pressure_pa=discharge_pressure_pa,
            inlet_temperature_k=inlet_temperature_k,
            polytropic_efficiency=blower_efficiency
        )
        shaft_power_kw = polytropic_result['shaft_power_kw']
        discharge_temperature_c = polytropic_result['discharge_temperature_c']
        aftercooling_heat_duty_kw = 0.0  # Typically not required for β < 1.5

    else:  # Adiabatic
        adiabatic_result = calculate_adiabatic_power(
            volumetric_flow_m3_s=volumetric_flow_m3_s,
            inlet_pressure_pa=inlet_pressure_pa,
            discharge_pressure_pa=discharge_pressure_pa,
            inlet_temperature_k=inlet_temperature_k,
            gamma=GAMMA_AIR,
            isentropic_efficiency=blower_efficiency
        )
        shaft_power_kw = adiabatic_result['shaft_power_kw']
        discharge_temperature_c = adiabatic_result['discharge_temperature_c']
        aftercooling_heat_duty_kw = adiabatic_result['aftercooling_heat_duty_kw']

    # Calculate motor power (accounts for motor efficiency)
    motor_power_kw = shaft_power_kw / motor_efficiency

    # Convert to horsepower
    motor_power_hp = motor_power_kw * 1.34102

    # Convert pressures to common units
    PSI_TO_PA = 6894.76
    discharge_pressure_psig = (discharge_pressure_pa - 101325.0) / PSI_TO_PA
    inlet_pressure_psig = (inlet_pressure_pa - 101325.0) / PSI_TO_PA

    logger.info(
        f"Blower sizing: {blower_type}, β={compression_ratio:.3f}, "
        f"P_discharge={discharge_pressure_psig:.2f} psig, "
        f"Motor={motor_power_kw:.2f} kW ({motor_power_hp:.1f} hp)"
    )

    return {
        # Blower selection
        'blower_type': blower_type,
        'thermodynamic_model': thermodynamic_model,
        'compression_ratio': compression_ratio,

        # Pressures
        'inlet_pressure_pa': inlet_pressure_pa,
        'inlet_pressure_psig': inlet_pressure_psig,
        'discharge_pressure_pa': discharge_pressure_pa,
        'discharge_pressure_psig': discharge_pressure_psig,

        # Temperatures
        'inlet_temperature_c': inlet_temperature_c,
        'discharge_temperature_c': discharge_temperature_c,
        'aftercooling_heat_duty_kw': aftercooling_heat_duty_kw,

        # Power
        'shaft_power_kw': shaft_power_kw,
        'motor_power_kw': motor_power_kw,
        'motor_power_hp': motor_power_hp,

        # Efficiencies
        'blower_efficiency': blower_efficiency,
        'motor_efficiency': motor_efficiency
    }
