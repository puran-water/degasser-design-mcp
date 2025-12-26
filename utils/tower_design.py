"""
Tower Design Module - Eckert Flooding and HTU/NTU Methods

Implements Perry's Chemical Engineers' Handbook correlations for:
1. Eckert Generalized Pressure Drop Correlation (GPDC) - flooding velocity
2. HTU/NTU method - tower height
3. Tower diameter and height calculations

References:
- Perry's Handbook 8th Ed, Section 14, Figures 14-55, 14-56
- Equations 14-140 to 14-142 (Eckert flooding)
- Equations 14-15 to 14-22 (HTU/NTU)
- Robbins correlation (Equations 14-145 to 14-151)
"""

import math
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Constants
G_GRAVITY = 9.81  # m/s²


def get_gpdc_flood_capacity(flow_parameter: float) -> float:
    """
    Get capacity parameter at flooding from GPDC Fig 14-55.

    Digitized flood line from Perry's Figure 14-55 (Eckert GPDC).

    NOTE: The nine data points below were digitized from Perry's Chemical Engineers'
    Handbook 8th Edition, Figure 14-55 (Eckert Generalized Pressure Drop Correlation).
    Source: Perry's Handbook Section 14, Equipment for Distillation and Gas Absorption.

    METHODOLOGY LIMITATION (for rigorous design):
    This implementation uses a digitized flood line for fast heuristic sizing.
    For rigorous design, the ΔP_flood intersection method should be used per
    Perry's Eq. 14-142: ΔP_flood = 0.12 × Fp^0.7, where Fp is the packing factor.
    The digitized approach is acceptable for preliminary/feasibility sizing.

    Args:
        flow_parameter: FLG = (L/G) * sqrt(ρG/ρL)

    Returns:
        Capacity parameter at flooding
    """
    # Digitized points from Perry's 8th Ed. Fig 14-55 flood line
    # (flow_parameter, capacity_parameter_flood)
    flood_line = [
        (0.01, 0.40),
        (0.02, 0.35),
        (0.05, 0.28),
        (0.1, 0.23),
        (0.2, 0.18),
        (0.5, 0.13),
        (1.0, 0.10),
        (2.0, 0.075),
        (5.0, 0.055)
    ]

    # Linear interpolation
    if flow_parameter <= flood_line[0][0]:
        return flood_line[0][1]
    if flow_parameter >= flood_line[-1][0]:
        return flood_line[-1][1]

    for i in range(len(flood_line) - 1):
        x1, y1 = flood_line[i]
        x2, y2 = flood_line[i + 1]
        if x1 <= flow_parameter <= x2:
            # Linear interpolation in log-log space (GPDC is log-log)
            log_x = math.log10(flow_parameter)
            log_x1 = math.log10(x1)
            log_x2 = math.log10(x2)
            log_y1 = math.log10(y1)
            log_y2 = math.log10(y2)

            log_y = log_y1 + (log_y2 - log_y1) * (log_x - log_x1) / (log_x2 - log_x1)
            return 10 ** log_y

    return 0.2  # Fallback


def calculate_eckert_flooding_velocity(
    liquid_rate: float,  # kg/(m²·s)
    gas_rate: float,  # kg/(m²·s)
    gas_density: float,  # kg/m³
    liquid_density: float,  # kg/m³
    liquid_viscosity_cp: float,  # cP (dynamic viscosity)
    packing_factor: float,  # m⁻¹
    surface_tension: float = 0.072  # N/m (water at 25°C)
) -> Dict[str, float]:
    """
    Calculate flooding velocity using Eckert GPDC with proper flow parameter.

    Perry's Equation (14-140):
    Capacity parameter = Ut * (ρG/(ρL - ρG))^0.5 * Fp^0.5 * ν^0.05

    Args:
        liquid_rate: Liquid mass velocity, kg/(m²·s)
        gas_rate: Gas mass velocity, kg/(m²·s)
        gas_density: Gas density, kg/m³
        liquid_density: Liquid density, kg/m³
        liquid_viscosity_cp: Liquid dynamic viscosity, cP
        packing_factor: Fp in m⁻¹
        surface_tension: N/m

    Returns:
        Dict with flooding and design parameters
    """
    # Convert dynamic viscosity (cP) to kinematic viscosity (cSt)
    # ν (cSt) = μ (cP) / ρ (g/cm³)
    # For SI: ν (m²/s) = μ (Pa·s) / ρ (kg/m³)
    mu_pa_s = liquid_viscosity_cp * 0.001  # cP to Pa·s
    nu_m2s = mu_pa_s / liquid_density  # m²/s
    nu_cs = nu_m2s * 1e6  # Convert to cSt (centistokes)

    # Flow parameter (FLG)
    # Perry's: FLG = (L/G) * (ρG/ρL)^0.5
    if gas_rate <= 0:
        # If no gas rate provided, estimate from typical air/water ratio
        gas_rate = liquid_rate * 0.05  # Assume 5% by mass (rough estimate)

    flow_parameter = (liquid_rate / gas_rate) * math.sqrt(gas_density / liquid_density)

    # Get capacity parameter at flood from GPDC
    capacity_param_flood = get_gpdc_flood_capacity(flow_parameter)

    # Perry's Eq 14-140: Capacity parameter = Ut * (ρG/(ρL - ρG))^0.5 * Fp^0.5 * ν^0.05
    # Solve for Ut (flood velocity):
    density_term = math.sqrt(gas_density / (liquid_density - gas_density))
    packing_term = math.sqrt(packing_factor)
    viscosity_term = nu_cs ** 0.05

    ut_flood = capacity_param_flood / (density_term * packing_term * viscosity_term)

    # F-factor at flood
    # Fs = Ut * ρG^0.5
    fs_flood = ut_flood * math.sqrt(gas_density)

    # Pressure drop at flood (Perry's Eq 14-142)
    delta_p_flood = 0.12 * (packing_factor ** 0.7)

    return {
        'flooding_velocity': ut_flood,  # m/s
        'f_factor_flood': fs_flood,  # m/s * (kg/m³)^0.5
        'flow_parameter': flow_parameter,
        'capacity_parameter': capacity_param_flood,
        'delta_p_flood': delta_p_flood,
        'design_velocity': ut_flood * 0.7,  # 70% of flood (typical)
        'design_f_factor': fs_flood * 0.7,
        'kinematic_viscosity_cs': nu_cs
    }


def calculate_tower_diameter(
    gas_flow_rate: float,  # m³/s
    design_velocity: float  # m/s
) -> Dict[str, float]:
    """
    Calculate tower diameter from gas flow rate and design velocity.

    Args:
        gas_flow_rate: Volumetric gas flow rate, m³/s
        design_velocity: Gas velocity (typically 70% of flooding), m/s

    Returns:
        Dict with diameter and cross-sectional area
    """
    # Cross-sectional area
    area = gas_flow_rate / design_velocity

    # Diameter from area
    diameter = math.sqrt(4 * area / math.pi)

    return {
        'diameter': diameter,  # m
        'cross_sectional_area': area,  # m²
        'design_velocity': design_velocity  # m/s
    }


def calculate_ntu_simple(
    inlet_concentration: float,
    outlet_concentration: float,
    henry_constant: float,
    air_water_ratio: float
) -> float:
    """
    Calculate number of transfer units (NTU) for stripping.

    Perry's Equation (14-22) simplified for dilute systems:
    NOG = ln[(y1 - y1*)/(y2 - y2*)]

    For stripping with clean air (y_gas_in = 0):
    NOG = ln[(C_in/C_out) * (1 - 1/S)] / (1 - 1/S)

    Where stripping factor S = (H * G) / L

    Simplified for high S (S >> 1):
    NOG ≈ ln(C_in / C_out)

    Args:
        inlet_concentration: Aqueous phase inlet (mol/L or ppm)
        outlet_concentration: Aqueous phase outlet (mol/L or ppm)
        henry_constant: Dimensionless H (Cgas/Caq)
        air_water_ratio: Volumetric air/water ratio

    Returns:
        Number of transfer units (NOG)
    """
    # Stripping factor S = (H * R * T * G/L)
    # For volumetric ratio and dimensionless H at standard conditions:
    # S ≈ H * air_water_ratio

    stripping_factor = henry_constant * air_water_ratio

    if stripping_factor > 10:
        # High stripping factor - simplified equation
        ntu = math.log(inlet_concentration / outlet_concentration)
    else:
        # General equation
        # NOG = ln[(y1-y1*)/(y2-y2*)]
        # For clean air: y2* = 0, y1* = x1/H
        # This requires more detailed mass balance
        # For now, use simplified form with correction
        removal_efficiency = 1.0 - (outlet_concentration / inlet_concentration)
        ntu = -math.log(1.0 - removal_efficiency * (1.0 - 1.0/stripping_factor))

    return ntu


def calculate_htu_from_packing_data(
    surface_area_m2_m3: float,
    void_fraction: float = 0.75,
    lambda_factor: float = 1.0,
    surface_tension_n_m: float = 0.072
) -> float:
    """
    Calculate HTU (Height of Transfer Unit) from packing properties.

    Perry's Equation 14-158: HETP = 93/ap
    where ap = surface area per unit volume (m²/m³)

    IMPORTANT: Perry's Eq. 14-158 was developed for organic/low surface tension
    systems (σ ≈ 20-30 mN/m). For aqueous systems (σ ≈ 72 mN/m), HETP must be
    doubled due to underwetting effects.

    References:
    - Perry's 8th Ed, Section 14, Eq. 14-158
    - Kister, Distillation Design: "×2 for water due to higher surface tension"
    - Billet & Schultes: Aqueous vs non-aqueous mass transfer integration

    For gas stripping (λ >> 1), HETP ≈ HOG
    Perry's Equation 14-153: HETP = HOG * ln(λ)/(λ-1)

    When λ >> 1 (stripping with high Henry's constant):
    ln(λ)/(λ-1) → 1/λ → 0, so HETP → HOG

    Simplified: HTU = HOG ≈ HETP for high λ (typical for CO2, H2S, VOC)

    Args:
        surface_area_m2_m3: Packing surface area per unit volume, m²/m³
        void_fraction: Void fraction (0-1), affects wetting
        lambda_factor: λ = m/(L/G) ratio (for stripping >> 1)
        surface_tension_n_m: Liquid surface tension, N/m (default 0.072 for water)

    Returns:
        HTU in meters (overall gas-phase basis, HOG)
    """
    # Perry's Eq 14-158: HETP = 93/ap (ap in m²/m³, HETP in m)
    # NOTE: This correlation is for organic systems (σ ≈ 25 mN/m)
    hetp = 93.0 / surface_area_m2_m3

    # For high lambda (stripping), HETP ≈ HOG
    # Apply correction for low lambda if needed
    if lambda_factor < 10:
        # Perry's Eq 14-153: HETP = HOG * ln(λ)/(λ-1)
        # Solve for HOG: HOG = HETP * (λ-1)/ln(λ)
        correction = (lambda_factor - 1.0) / math.log(lambda_factor)
        hog = hetp * correction
    else:
        # High lambda: HETP ≈ HOG
        hog = hetp

    # Apply wetting efficiency factor (simplified)
    # Low void fraction → better wetting → lower HTU
    # High void fraction → worse wetting → higher HTU
    wetting_factor = 1.0 + 0.2 * (void_fraction - 0.75)  # Reference: ε=0.75

    # Aqueous correction factor (Perry's Section 14 note, Kister)
    # Eq. 14-158 was developed for organic systems (σ ≈ 25 mN/m)
    # For water (σ ≈ 72 mN/m), underwetting increases HETP by ~2×
    # Threshold: σ > 50 mN/m triggers aqueous correction
    AQUEOUS_THRESHOLD_N_M = 0.050  # 50 mN/m
    if surface_tension_n_m > AQUEOUS_THRESHOLD_N_M:
        aqueous_correction = 2.0
        logger.info(
            f"Applying aqueous correction factor ×{aqueous_correction} "
            f"for σ={surface_tension_n_m*1000:.0f} mN/m (water system)"
        )
    else:
        aqueous_correction = 1.0

    htu = hog * wetting_factor * aqueous_correction

    # Sanity check: HTU should be 0.3 to 6.0 m for typical packings
    # Upper bound increased for aqueous systems with correction applied
    htu = max(0.3, min(6.0, htu))

    return htu


def calculate_htu_correlation(
    packing_type: str,
    packing_size_mm: float,
    liquid_rate: float,  # m³/(m²·h)
    gas_rate: float  # m³/(m²·h)
) -> float:
    """
    Estimate HTU (Height of Transfer Unit) from correlations.

    DEPRECATED: Use calculate_htu_from_packing_data() with actual packing properties.

    This function provides a fallback if packing data is not available.

    Perry's Section 14 provides empirical correlations:
    - For Pall rings: HETP = 93/ap (Equation 14-158)
      where ap = surface area per volume (m²/m³)
    - Typical HTU ≈ HETP for stripping (high λ)

    Args:
        packing_type: Type of packing (e.g., "pall_rings", "raschig_rings")
        packing_size_mm: Nominal packing size in mm
        liquid_rate: Liquid flow rate, m³/(m²·h)
        gas_rate: Gas flow rate, m³/(m²·h)

    Returns:
        HTU in meters (overall gas-phase basis, HOG)
    """
    # Fallback: estimate surface area from packing size
    # Rough approximation for random packing:
    # ap ≈ 300/size_mm (for size in mm)

    estimated_surface_area = 300.0 / packing_size_mm  # m²/m³

    # Use Perry's correlation
    htu = calculate_htu_from_packing_data(estimated_surface_area)

    logger.warning(f"Using estimated HTU from packing size. "
                   f"Prefer using actual packing data from pack.json.")

    return htu


def calculate_tower_height(
    ntu: float,
    htu: float,
    packing_safety_factor: float = 1.2
) -> Dict[str, float]:
    """
    Calculate tower height from NTU and HTU.

    Perry's Equation (14-15):
    hT = HOG * NOG

    Args:
        ntu: Number of transfer units
        htu: Height of transfer unit, m
        packing_safety_factor: Safety factor (typical 1.1-1.3)

    Returns:
        Dict with tower height and components
    """
    # Basic height
    height_theoretical = ntu * htu

    # Add safety factor
    height_design = height_theoretical * packing_safety_factor

    # Add disengagement space (10% of height, minimum 0.5 m)
    disengagement = max(0.5, 0.1 * height_design)

    total_height = height_design + disengagement

    return {
        'theoretical_height': height_theoretical,  # m
        'design_height': height_design,  # m
        'disengagement_space': disengagement,  # m
        'total_height': total_height,  # m
        'ntu': ntu,
        'htu': htu
    }


def design_stripping_tower(
    application: str,  # "CO2", "H2S", or "VOC"
    water_flow_rate: float,  # m³/h
    inlet_concentration: float,  # mg/L or ppm
    outlet_concentration: float,  # mg/L or ppm
    henry_constant: float,  # dimensionless
    air_water_ratio: float,  # volumetric
    temperature_c: float = 25.0,
    packing_id: Optional[str] = None,
    packing_type: str = "pall_rings",  # Deprecated - use packing_id
    packing_size_mm: float = 50.0  # Deprecated - use packing_id
) -> Dict[str, Any]:
    """
    Complete heuristic design of stripping tower using actual packing data.

    Args:
        application: Type of stripping ("CO2", "H2S", "VOC")
        water_flow_rate: Water flow rate, m³/h
        inlet_concentration: Inlet concentration, mg/L
        outlet_concentration: Outlet concentration, mg/L
        henry_constant: Dimensionless Henry's constant
        air_water_ratio: Volumetric air/water ratio
        temperature_c: Temperature, °C
        packing_id: Packing ID from pack.json (e.g., "Metal_Pall_Rings_50mm")
                   If None, uses default packing for application
        packing_type: DEPRECATED - use packing_id instead
        packing_size_mm: DEPRECATED - use packing_id instead

    Returns:
        Complete tower design dict
    """
    # Import packing properties module
    from .packing_properties import get_packing_by_id, get_default_packing

    # Get packing data
    if packing_id:
        packing = get_packing_by_id(packing_id)
        if not packing:
            logger.warning(f"Packing ID '{packing_id}' not found, using default")
            packing = get_default_packing(application)
    else:
        # Use default packing for application
        packing = get_default_packing(application)

    # Extract packing properties
    packing_name = packing['name']
    packing_size_mm = packing['nominal_size_mm']
    packing_factor = packing['packing_factor_m_inv']
    surface_area = packing['surface_area_m2_m3']
    void_fraction = packing['void_fraction']

    # Air flow rate
    air_flow_rate = water_flow_rate * air_water_ratio  # m³/h

    # Calculate NTU
    ntu = calculate_ntu_simple(
        inlet_concentration,
        outlet_concentration,
        henry_constant,
        air_water_ratio
    )

    # Calculate lambda factor for HTU correction
    # λ = m/(L/G) = H * (G/L) for stripping
    lambda_factor = henry_constant * air_water_ratio

    # Calculate HTU from actual packing data (Perry's Eq 14-158)
    htu = calculate_htu_from_packing_data(
        surface_area,
        void_fraction,
        lambda_factor
    )

    # Tower height
    height_results = calculate_tower_height(ntu, htu)

    # For diameter, estimate liquid and gas loading
    # Use typical properties for air-water system
    gas_density = 1.2  # kg/m³ (air at 25°C)
    liquid_density = 997.0  # kg/m³ (water at 25°C)
    liquid_viscosity = 0.89  # cP (water at 25°C)

    # Estimate cross-sectional area from water flow rate
    # Typical liquid loading: 10-30 m³/(m²·h)
    liquid_loading = 20.0  # m³/(m²·h) - middle of range
    estimated_area = water_flow_rate / liquid_loading  # m²

    # Liquid mass flux
    liquid_rate = (water_flow_rate / estimated_area) * liquid_density / 3600.0  # kg/(m²·s)

    # Gas mass flux (approximate from volumetric flow)
    gas_rate = (air_flow_rate / estimated_area) * gas_density / 3600.0  # kg/(m²·s)

    # Flooding calculation with actual packing factor
    flood_results = calculate_eckert_flooding_velocity(
        liquid_rate=liquid_rate,
        gas_rate=gas_rate,
        gas_density=gas_density,
        liquid_density=liquid_density,
        liquid_viscosity_cp=liquid_viscosity,
        packing_factor=packing_factor
    )

    # Tower diameter from air flow
    air_flow_m3s = air_flow_rate / 3600.0  # Convert to m³/s
    diameter_results = calculate_tower_diameter(
        air_flow_m3s,
        flood_results['design_velocity']
    )

    return {
        'application': application,
        'tower_diameter': diameter_results['diameter'],
        'tower_height': height_results['total_height'],
        'packing_height': height_results['design_height'],
        'packing_id': packing.get('packing_id', packing_id),
        'packing_name': packing_name,
        'packing_size_mm': packing_size_mm,
        'packing_factor': packing_factor,
        'packing_surface_area': surface_area,
        'air_flow_rate': air_flow_rate,
        'water_flow_rate': water_flow_rate,
        'air_water_ratio': air_water_ratio,
        'ntu': ntu,
        'htu': htu,
        'lambda_factor': lambda_factor,
        'design_velocity': flood_results['design_velocity'],
        'flooding_velocity': flood_results['flooding_velocity'],
        'flow_parameter': flood_results['flow_parameter'],
        'removal_efficiency': (1.0 - outlet_concentration/inlet_concentration) * 100
    }
