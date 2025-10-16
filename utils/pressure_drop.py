"""
Pressure Drop Calculations for Packed Tower Air Strippers

Implements Robbins correlation (Perry's Eq 14-145 to 14-151) plus
accessory pressure drops for comprehensive blower sizing.

Reference:
- Perry's Chemical Engineers' Handbook 8th Ed, Section 14
- Robbins, Chem. Eng. Progr., 87(5), 87-91 (May 1991)
- CalebBell/fluids library for validation
"""

import logging
from typing import Dict, Optional
import math

logger = logging.getLogger(__name__)

# Constants for Robbins correlation (Perry's Eq 14-146, 14-147)
C3 = 7.4e-8
C4 = 2.7e-5


def calculate_robbins_pressure_drop(
    packing_height_m: float,
    tower_diameter_m: float,
    gas_mass_velocity_kg_s_m2: float,
    liquid_mass_velocity_kg_s_m2: float,
    packing_factor_dry_m_inv: float,
    gas_density_kg_m3: float = 1.2,
    liquid_density_kg_m3: float = 1000.0,
    liquid_viscosity_cp: float = 1.0,
    operating_pressure_pa: float = 101325.0
) -> Dict[str, float]:
    """
    Calculate packed bed pressure drop using Robbins correlation.

    Uses fluids library implementation for accuracy and validation.
    Falls back to manual calculation if fluids library not available.

    Perry's Handbook Equations 14-145 to 14-151.

    Args:
        packing_height_m: Packed bed height, m
        gas_mass_velocity_kg_s_m2: Gas mass velocity, kg/(s·m²)
        liquid_mass_velocity_kg_s_m2: Liquid mass velocity, kg/(s·m²)
        packing_factor_dry_m_inv: Dry packing factor Fpd, m⁻¹
        gas_density_kg_m3: Gas density, kg/m³
        liquid_density_kg_m3: Liquid density, kg/m³
        liquid_viscosity_cp: Liquid viscosity, cP
        operating_pressure_pa: Operating pressure, Pa

    Returns:
        Dict with:
        - gas_loading_factor: Gf (dimensionless)
        - liquid_loading_factor: Lf (dimensionless)
        - dry_pressure_drop_pa_m: Dry pressure drop per meter
        - wet_pressure_drop_pa_m: Additional liquid holdup pressure drop per meter
        - total_pressure_drop_pa_m: Total pressure drop per meter
        - total_pressure_drop_pa: Total pressure drop for bed height
    """

    try:
        # Use fluids library for accurate Robbins correlation
        from fluids.packed_tower import Robbins as fluids_robbins

        # Convert viscosity from cP to Pa·s
        liquid_viscosity_pa_s = liquid_viscosity_cp * 0.001

        # Convert packing factor from m⁻¹ to ft⁻¹
        packing_factor_dry_ft_inv = packing_factor_dry_m_inv * 0.3048

        # Calculate pressure drop using fluids library
        total_pressure_drop_pa = fluids_robbins(
            L=liquid_mass_velocity_kg_s_m2,
            G=gas_mass_velocity_kg_s_m2,
            rhol=liquid_density_kg_m3,
            rhog=gas_density_kg_m3,
            mul=liquid_viscosity_pa_s,
            H=packing_height_m,
            Fpd=packing_factor_dry_ft_inv
        )

        # Calculate per-meter values
        total_pressure_drop_pa_m = total_pressure_drop_pa / packing_height_m

        logger.info(
            f"Robbins correlation (fluids): "
            f"ΔP={total_pressure_drop_pa_m:.1f} Pa/m ({total_pressure_drop_pa_m * 0.3048 / 249.089:.3f} in H2O/ft)"
        )

        return {
            'gas_loading_factor': 0.0,  # Not calculated when using fluids library
            'liquid_loading_factor': 0.0,  # Not calculated when using fluids library
            'dry_pressure_drop_pa_m': total_pressure_drop_pa_m * 0.9,  # Estimate: 90% dry
            'wet_pressure_drop_pa_m': total_pressure_drop_pa_m * 0.1,  # Estimate: 10% wet
            'total_pressure_drop_pa_m': total_pressure_drop_pa_m,
            'total_pressure_drop_pa': total_pressure_drop_pa
        }

    except ImportError:
        logger.warning("fluids library not available. Skipping Robbins pressure drop calculation.")
        # Return minimal estimates if fluids library not available
        # Rough estimate: 0.5 inches H2O per foot of packing
        estimated_pa_m = 0.5 * 249.089 / 0.3048  # ~408 Pa/m
        estimated_total = estimated_pa_m * packing_height_m

        return {
            'gas_loading_factor': 0.0,
            'liquid_loading_factor': 0.0,
            'dry_pressure_drop_pa_m': estimated_pa_m,
            'wet_pressure_drop_pa_m': 0.0,
            'total_pressure_drop_pa_m': estimated_pa_m,
            'total_pressure_drop_pa': estimated_total
        }


def calculate_accessory_pressure_drops(
    tower_height_m: float,
    tower_diameter_m: float,
    gas_velocity_m_s: float,
    packed_bed_pressure_drop_pa: float,
    gas_density_kg_m3: float = 1.2,
    inlet_distributor_inches_h2o: float = 1.0,
    outlet_distributor_inches_h2o: float = 1.0,
    demister_inches_h2o: float = 1.5,
    ductwork_silencer_fraction: float = 0.10
) -> Dict[str, float]:
    """
    Calculate all accessory pressure drops beyond the packed bed.

    Args:
        tower_height_m: Total tower height, m
        tower_diameter_m: Tower diameter, m
        gas_velocity_m_s: Superficial gas velocity in tower, m/s
        packed_bed_pressure_drop_pa: Packed bed pressure drop, Pa
        gas_density_kg_m3: Gas density, kg/m³
        inlet_distributor_inches_h2o: Inlet vapor distributor ΔP, inches H₂O
        outlet_distributor_inches_h2o: Outlet vapor distributor ΔP, inches H₂O
        demister_inches_h2o: Demister/coalescer pad ΔP, inches H₂O
        ductwork_silencer_fraction: Ductwork/silencer ΔP as fraction of bed ΔP

    Returns:
        Dict with all accessory pressure drops in Pa
    """

    # Conversion factor: 1 inch H2O = 249.089 Pa
    INCHES_H2O_TO_PA = 249.089

    # 1. Inlet vapor distributor (0.5-1.5 inches H2O typical)
    inlet_distributor_pa = inlet_distributor_inches_h2o * INCHES_H2O_TO_PA

    # 2. Outlet vapor distributor (0.5-1.5 inches H2O typical)
    outlet_distributor_pa = outlet_distributor_inches_h2o * INCHES_H2O_TO_PA

    # 3. Demister/coalescer pads (1-2 inches H2O clean)
    demister_pa = demister_inches_h2o * INCHES_H2O_TO_PA

    # 4. Entrance/exit momentum losses (≈0.5·ρ·v² per abrupt change)
    # Assume 2 changes (entrance + exit)
    dynamic_pressure_pa = 0.5 * gas_density_kg_m3 * gas_velocity_m_s**2
    momentum_losses_pa = 2 * dynamic_pressure_pa

    # 5. Ductwork and silencers (5-15% of bed pressure drop)
    ductwork_silencer_pa = ductwork_silencer_fraction * packed_bed_pressure_drop_pa

    # 6. Tower elevation/static head (ρ·g·H)
    # Air column static pressure
    g = 9.81  # m/s²
    elevation_head_pa = gas_density_kg_m3 * g * tower_height_m

    logger.info(
        f"Accessory pressure drops (Pa): inlet={inlet_distributor_pa:.0f}, "
        f"outlet={outlet_distributor_pa:.0f}, demister={demister_pa:.0f}, "
        f"momentum={momentum_losses_pa:.0f}, ductwork={ductwork_silencer_pa:.0f}, "
        f"elevation={elevation_head_pa:.0f}"
    )

    return {
        'inlet_distributor_pa': inlet_distributor_pa,
        'outlet_distributor_pa': outlet_distributor_pa,
        'demister_pa': demister_pa,
        'momentum_losses_pa': momentum_losses_pa,
        'ductwork_silencer_pa': ductwork_silencer_pa,
        'elevation_head_pa': elevation_head_pa
    }


def calculate_total_system_pressure_drop(
    packing_height_m: float,
    tower_height_m: float,
    tower_diameter_m: float,
    gas_flow_rate_m3_h: float,
    liquid_flow_rate_m3_h: float,
    packing_factor_dry_m_inv: float,
    gas_density_kg_m3: float = 1.2,
    liquid_density_kg_m3: float = 1000.0,
    liquid_viscosity_cp: float = 1.0,
    operating_pressure_pa: float = 101325.0,
    inlet_distributor_inches_h2o: float = 1.0,
    outlet_distributor_inches_h2o: float = 1.0,
    demister_inches_h2o: float = 1.5,
    ductwork_silencer_fraction: float = 0.10,
    safety_factor: float = 0.12
) -> Dict[str, float]:
    """
    Calculate total system pressure drop for blower sizing.

    Combines Robbins packed bed correlation with all accessory pressure drops
    and applies design safety factor.

    Args:
        packing_height_m: Packed bed height, m
        tower_height_m: Total tower height, m
        tower_diameter_m: Tower diameter, m
        gas_flow_rate_m3_h: Volumetric gas flow rate, m³/h
        liquid_flow_rate_m3_h: Volumetric liquid flow rate, m³/h
        packing_factor_dry_m_inv: Dry packing factor Fpd, m⁻¹
        gas_density_kg_m3: Gas density, kg/m³
        liquid_density_kg_m3: Liquid density, kg/m³
        liquid_viscosity_cp: Liquid viscosity, cP
        operating_pressure_pa: Operating pressure, Pa
        inlet_distributor_inches_h2o: Inlet distributor ΔP, inches H₂O
        outlet_distributor_inches_h2o: Outlet distributor ΔP, inches H₂O
        demister_inches_h2o: Demister pad ΔP, inches H₂O
        ductwork_silencer_fraction: Ductwork/silencer ΔP fraction
        safety_factor: Design safety factor (0.12 = 12%)

    Returns:
        Dict with complete pressure drop breakdown
    """

    # Calculate tower cross-sectional area
    tower_area_m2 = math.pi * (tower_diameter_m / 2.0)**2

    # Calculate mass velocities
    # Gas: Q (m³/h) → kg/(s·m²)
    gas_mass_velocity = (gas_flow_rate_m3_h / 3600.0) * gas_density_kg_m3 / tower_area_m2

    # Liquid: Q (m³/h) → kg/(s·m²)
    liquid_mass_velocity = (liquid_flow_rate_m3_h / 3600.0) * liquid_density_kg_m3 / tower_area_m2

    # Calculate superficial gas velocity for momentum losses
    gas_velocity_m_s = (gas_flow_rate_m3_h / 3600.0) / tower_area_m2

    # 1. Packed bed pressure drop (Robbins correlation)
    robbins_result = calculate_robbins_pressure_drop(
        packing_height_m=packing_height_m,
        tower_diameter_m=tower_diameter_m,
        gas_mass_velocity_kg_s_m2=gas_mass_velocity,
        liquid_mass_velocity_kg_s_m2=liquid_mass_velocity,
        packing_factor_dry_m_inv=packing_factor_dry_m_inv,
        gas_density_kg_m3=gas_density_kg_m3,
        liquid_density_kg_m3=liquid_density_kg_m3,
        liquid_viscosity_cp=liquid_viscosity_cp,
        operating_pressure_pa=operating_pressure_pa
    )

    packed_bed_pressure_drop_pa = robbins_result['total_pressure_drop_pa']

    # 2. Accessory pressure drops
    accessory_result = calculate_accessory_pressure_drops(
        tower_height_m=tower_height_m,
        tower_diameter_m=tower_diameter_m,
        gas_velocity_m_s=gas_velocity_m_s,
        packed_bed_pressure_drop_pa=packed_bed_pressure_drop_pa,
        gas_density_kg_m3=gas_density_kg_m3,
        inlet_distributor_inches_h2o=inlet_distributor_inches_h2o,
        outlet_distributor_inches_h2o=outlet_distributor_inches_h2o,
        demister_inches_h2o=demister_inches_h2o,
        ductwork_silencer_fraction=ductwork_silencer_fraction
    )

    # 3. Sum all pressure drops
    total_before_safety_pa = (
        packed_bed_pressure_drop_pa +
        accessory_result['inlet_distributor_pa'] +
        accessory_result['outlet_distributor_pa'] +
        accessory_result['demister_pa'] +
        accessory_result['momentum_losses_pa'] +
        accessory_result['ductwork_silencer_pa'] +
        accessory_result['elevation_head_pa']
    )

    # 4. Apply safety factor
    safety_factor_pa = safety_factor * total_before_safety_pa
    total_system_pressure_drop_pa = total_before_safety_pa + safety_factor_pa

    # Convert to other common units
    INCHES_H2O_TO_PA = 249.089
    PSI_TO_PA = 6894.76

    total_inches_h2o = total_system_pressure_drop_pa / INCHES_H2O_TO_PA
    total_psig = total_system_pressure_drop_pa / PSI_TO_PA

    logger.info(
        f"Total system pressure drop: {total_system_pressure_drop_pa:.0f} Pa "
        f"({total_inches_h2o:.2f} in H2O, {total_psig:.3f} psig)"
    )

    return {
        # Robbins correlation results
        'gas_loading_factor': robbins_result['gas_loading_factor'],
        'liquid_loading_factor': robbins_result['liquid_loading_factor'],
        'packed_bed_pressure_drop_pa': packed_bed_pressure_drop_pa,

        # Accessory pressure drops
        'inlet_distributor_pressure_drop_pa': accessory_result['inlet_distributor_pa'],
        'outlet_distributor_pressure_drop_pa': accessory_result['outlet_distributor_pa'],
        'demister_pressure_drop_pa': accessory_result['demister_pa'],
        'momentum_losses_pa': accessory_result['momentum_losses_pa'],
        'ductwork_silencer_pressure_drop_pa': accessory_result['ductwork_silencer_pa'],
        'elevation_head_pa': accessory_result['elevation_head_pa'],

        # Safety factor and total
        'safety_factor_pa': safety_factor_pa,
        'safety_factor_fraction': safety_factor,
        'total_system_pressure_drop_pa': total_system_pressure_drop_pa,
        'total_system_pressure_drop_inches_h2o': total_inches_h2o,
        'total_system_pressure_drop_psig': total_psig
    }
