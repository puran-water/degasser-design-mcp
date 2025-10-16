"""
Heuristic Sizing MCP Tool

Provides fast (<1s) heuristic sizing for packed tower air strippers.
Uses Perry's Handbook correlations (Eckert GPDC, HTU/NTU method).

Applications:
- CO2 stripping (alkalinity removal)
- H2S stripping (sulfide removal)
- VOC stripping (volatile organic removal)

Reference:
- Perry's Chemical Engineers' Handbook 8th Ed, Section 14
- Eckert GPDC: Figures 14-55, 14-56, Equations 14-140 to 14-142
- HTU/NTU: Equations 14-15 to 14-22, 14-153, 14-158
"""

import logging
from typing import Dict, Any

from .schemas import HeuristicSizingInput, HeuristicSizingResult, Tier1Outcome
from utils.water_chemistry import WaterChemistryData, prepare_water_chemistry

logger = logging.getLogger(__name__)


# Default Henry's constants (dimensionless, Cgas/Caq at 25°C)
DEFAULT_HENRY_CONSTANTS = {
    "CO2": 0.83,  # CO2 in water at 25°C
    "H2S": 0.41,  # H2S in water at 25°C
    "VOC": 8.59,  # TCE as representative VOC
    "general": 1.0  # Generic default
}

# Molecular weights (g/mol) for common applications
DEFAULT_MOLECULAR_WEIGHTS = {
    "CO2": 44.01,
    "H2S": 34.08,
    "VOC": 131.388,  # TCE as representative
    "general": 100.0  # Generic estimate
}

# PHREEQC gas phase names (must match defined phases)
PHREEQC_GAS_PHASES = {
    "CO2": "CO2(g)",  # Built-in PHREEQC phase
    "H2S": "H2S(g)",  # Built-in PHREEQC phase
    "VOC": "TCE(g)",  # Custom phase from voc_phases.dat
    "general": "TCE(g)"  # Default to TCE
}


async def heuristic_sizing(
    application: str,
    water_flow_rate_m3_h: float,
    inlet_concentration_mg_L: float,
    outlet_concentration_mg_L: float,
    air_water_ratio: float = 30.0,
    temperature_c: float = 25.0,
    packing_id: str = None,
    henry_constant_25C: float = None,
    water_ph: float = None,
    water_chemistry_json: str = None,
    include_blower_sizing: bool = True,
    blower_efficiency_override: float = None,
    motor_efficiency: float = 0.92
) -> Dict[str, Any]:
    """
    Perform heuristic sizing of packed tower air stripper.

    Fast (<1s) preliminary design using Perry's correlations.
    Suitable for feasibility studies and initial cost estimates.

    Args:
        application: Application type ("CO2", "H2S", "VOC", "general")
        water_flow_rate_m3_h: Water flow rate, m³/h
        inlet_concentration_mg_L: Inlet concentration, mg/L
        outlet_concentration_mg_L: Outlet concentration, mg/L
        air_water_ratio: Volumetric air/water ratio (default: 30)
        temperature_c: Temperature, °C (default: 25)
        packing_id: Packing from catalog (default: application-specific)
        henry_constant_25C: Henry's constant override (default: from application)
        water_ph: Water pH for speciation (H2S/CO2 only, default: None)
        water_chemistry_json: Optional water chemistry JSON string compatible with
            the RO design MCP (ion concentrations in mg/L). Provides PHREEQC with
            realistic counter-ions. Defaults to municipal template if omitted.
        include_blower_sizing: Include blower specs in output (default: True)
        blower_efficiency_override: Override default blower efficiency (default: None)
        motor_efficiency: Electric motor efficiency, 0-1 (default: 0.92)

    Returns:
        Dict with tower dimensions, packing specs, performance metrics, and
        optional blower specifications

    Example:
        >>> result = await heuristic_sizing(
        ...     application="VOC",
        ...     water_flow_rate_m3_h=100.0,
        ...     inlet_concentration_mg_L=38.0,
        ...     outlet_concentration_mg_L=0.00151,
        ...     air_water_ratio=30.0,
        ...     henry_constant_25C=8.59,
        ...     include_blower_sizing=True
        ... )
        >>> print(f"Tower: {result['tower_diameter_m']:.1f}m dia x {result['tower_height_m']:.1f}m")
        >>> print(f"Blower: {result['blower_specs']['motor_power_hp']:.1f} hp")
    """
    # Validate and parse input
    input_data = HeuristicSizingInput(
        application=application,
        water_flow_rate_m3_h=water_flow_rate_m3_h,
        inlet_concentration_mg_L=inlet_concentration_mg_L,
        outlet_concentration_mg_L=outlet_concentration_mg_L,
        air_water_ratio=air_water_ratio,
        temperature_c=temperature_c,
        packing_id=packing_id,
        henry_constant_25C=henry_constant_25C,
        water_ph=water_ph,
        water_chemistry_json=water_chemistry_json
    )

    # Parse/prepare water chemistry (default municipal background when absent)
    water_chemistry_data: WaterChemistryData = prepare_water_chemistry(
        input_data.water_chemistry_json
    )

    if water_chemistry_data.source != "user":
        logger.info(
            "Tier 1 using %s background ions (charge imbalance %.2f%%).",
            water_chemistry_data.source,
            water_chemistry_data.charge_balance_percent,
        )
    else:
        logger.info(
            "Water chemistry provided with charge imbalance %.2f%%.",
            water_chemistry_data.charge_balance_percent
        )

    # Resolve Henry's constant
    henry_constant = input_data.henry_constant_25C
    if henry_constant is None:
        # Use default for application
        henry_constant = DEFAULT_HENRY_CONSTANTS.get(
            input_data.application.upper(),
            DEFAULT_HENRY_CONSTANTS["general"]
        )
        logger.info(
            f"Using default Henry's constant for {input_data.application}: "
            f"H = {henry_constant}"
        )

    # Import tower design module
    import sys
    from pathlib import Path

    # Add parent directory to path for imports
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from utils.tower_design import design_stripping_tower
    from utils.speciation import strippable_fraction
    from utils.pressure_drop import calculate_total_system_pressure_drop
    from utils.blower_sizing import calculate_blower_power
    from utils.packing_properties import load_packing_catalog
    from tools.schemas import BlowerSpecifications, DesignWarning

    # Apply pH-dependent speciation for H2S and CO2
    effective_inlet = input_data.inlet_concentration_mg_L
    effective_outlet = input_data.outlet_concentration_mg_L
    strippable_frac = 1.0  # Default: 100% strippable (VOC case)
    non_strippable_inlet = 0.0

    if input_data.water_ph is not None and input_data.application.upper() in ["H2S", "CO2"]:
        # Calculate strippable fraction
        strippable_frac = strippable_fraction(
            solute=input_data.application,
            ph=input_data.water_ph,
            temp_c=input_data.temperature_c,
            total_mg_l=input_data.inlet_concentration_mg_L
        )

        # Split inlet into strippable and non-strippable portions
        strippable_inlet = input_data.inlet_concentration_mg_L * strippable_frac
        non_strippable_inlet = input_data.inlet_concentration_mg_L * (1 - strippable_frac)

        # Design tower to strip only the strippable fraction
        # Non-strippable portion passes through unchanged
        effective_inlet = strippable_inlet
        effective_outlet = max(
            input_data.outlet_concentration_mg_L - non_strippable_inlet,
            0.01  # Minimum 0.01 mg/L to avoid division by zero in NTU calculation
        )

        logger.info(
            f"pH-dependent speciation for {input_data.application} at pH {input_data.water_ph:.2f}: "
            f"{strippable_frac*100:.1f}% strippable "
            f"({strippable_inlet:.2f} mg/L strippable, {non_strippable_inlet:.2f} mg/L non-strippable)"
        )

        logger.info(
            f"Design basis: Strip {effective_inlet:.2f} mg/L → {effective_outlet:.2f} mg/L "
            f"(Total outlet will be ~{effective_outlet + non_strippable_inlet:.2f} mg/L)"
        )

        # Warn if outlet target is unachievable due to non-strippable fraction
        if non_strippable_inlet > input_data.outlet_concentration_mg_L:
            logger.warning(
                f"Target outlet ({input_data.outlet_concentration_mg_L:.2f} mg/L) is unachievable at pH {input_data.water_ph:.2f}. "
                f"Non-strippable fraction alone is {non_strippable_inlet:.2f} mg/L. "
                f"Minimum achievable outlet: ~{non_strippable_inlet:.2f} mg/L. "
                f"Consider pH adjustment to improve stripping efficiency."
            )
        elif strippable_frac < 0.2:
            logger.warning(
                f"Low strippable fraction ({strippable_frac*100:.1f}%) at pH {input_data.water_ph:.2f}. "
                f"Consider pH adjustment to improve stripping efficiency."
            )

    # Initialize warnings list for structured warnings
    warnings_list = []

    # Check for pH drift risk (critical for neutral/alkaline pH)
    if input_data.water_ph is not None and input_data.water_ph >= 7.0:
        if input_data.application.upper() in ["H2S", "CO2"]:
            # Calculate apparent stripping factor
            lambda_app = strippable_frac * henry_constant * input_data.air_water_ratio

            # Warn if weak driving force (indicates high pH drift sensitivity)
            if lambda_app < 2.5:
                severity = "critical" if lambda_app < 2.0 else "warning"

                ph_drift_warning = DesignWarning(
                    severity=severity,
                    category="ph_drift",
                    message=(
                        f"Operating at pH {input_data.water_ph:.1f} without acid control. "
                        f"This heuristic assumes FIXED pH throughout tower. "
                        f"Reality: pH will rise as CO₂ strips → strippable fraction falls. "
                        f"Apparent λ = {lambda_app:.2f} (barely favorable)."
                    ),
                    recommendations=[
                        f"Acidify feed to pH 5.5-6.5 (reduces tower height 3-5×)",
                        f"Use Tier 2 simulation tool for accurate pH-coupled sizing",
                        f"Consider distributed acid dosing along tower height",
                        f"Budget for taller tower: estimated height may be 2-3× actual value"
                    ],
                    estimated_error_range="50-200% height underestimate"
                )
                warnings_list.append(ph_drift_warning)

                # Also log for CLI users
                logger.warning(
                    f"⚠️  {'CRITICAL' if severity == 'critical' else 'WARNING'} pH DRIFT RISK:\n"
                    f"   {ph_drift_warning.message}\n"
                    f"   Recommendations:\n" +
                    "\n".join(f"     • {rec}" for rec in ph_drift_warning.recommendations)
                )

    # Call heuristic sizing engine
    try:
        design_result = design_stripping_tower(
            application=input_data.application,
            water_flow_rate=input_data.water_flow_rate_m3_h,
            inlet_concentration=effective_inlet,  # pH-corrected strippable inlet
            outlet_concentration=effective_outlet,  # pH-corrected strippable outlet
            henry_constant=henry_constant,
            air_water_ratio=input_data.air_water_ratio,
            temperature_c=input_data.temperature_c,
            packing_id=input_data.packing_id
        )

        # Convert to output schema
        result = HeuristicSizingResult(
            tower_diameter_m=design_result['tower_diameter'],
            tower_height_m=design_result['tower_height'],
            packing_height_m=design_result['packing_height'],
            packing_id=design_result['packing_id'],
            packing_name=design_result['packing_name'],
            packing_size_mm=design_result['packing_size_mm'],
            packing_factor_m_inv=design_result['packing_factor'],
            packing_surface_area_m2_m3=design_result['packing_surface_area'],
            design_velocity_m_s=design_result['design_velocity'],
            flooding_velocity_m_s=design_result['flooding_velocity'],
            ntu=design_result['ntu'],
            htu_m=design_result['htu'],
            lambda_factor=design_result['lambda_factor'],
            air_flow_rate_m3_h=design_result['air_flow_rate'],
            water_flow_rate_m3_h=design_result['water_flow_rate'],
            air_water_ratio=design_result['air_water_ratio'],
            removal_efficiency_percent=design_result['removal_efficiency'],
            flow_parameter=design_result.get('flow_parameter'),
            capacity_parameter=None,  # Not currently returned by design_stripping_tower
            warnings=warnings_list  # Add structured warnings
        )

        # Add blower sizing if requested
        if include_blower_sizing:
            try:
                # Get packing properties for pressure drop calculation
                catalog = load_packing_catalog()
                packing_props = catalog.get(design_result['packing_id'])

                if packing_props is None:
                    logger.warning(f"Packing {design_result['packing_id']} not found in catalog. Skipping blower sizing.")
                else:
                    # Get dry packing factor (Fpd) - use packing_factor_m_inv from catalog
                    packing_factor_dry = packing_props.get('packing_factor_m_inv', design_result['packing_factor'])

                    # Calculate total system pressure drop
                    pressure_drop_result = calculate_total_system_pressure_drop(
                        packing_height_m=design_result['packing_height'],
                        tower_height_m=design_result['tower_height'],
                        tower_diameter_m=design_result['tower_diameter'],
                        gas_flow_rate_m3_h=design_result['air_flow_rate'],
                        liquid_flow_rate_m3_h=design_result['water_flow_rate'],
                        packing_factor_dry_m_inv=packing_factor_dry,
                        gas_density_kg_m3=1.2,  # Air at 25°C
                        liquid_density_kg_m3=1000.0,  # Water
                        liquid_viscosity_cp=1.0,  # Water at 25°C
                        operating_pressure_pa=101325.0,  # Atmospheric
                        inlet_distributor_inches_h2o=1.0,
                        outlet_distributor_inches_h2o=1.0,
                        demister_inches_h2o=1.5,
                        ductwork_silencer_fraction=0.10,
                        safety_factor=0.12
                    )

                    # Calculate blower power
                    blower_result = calculate_blower_power(
                        air_flow_rate_m3_h=design_result['air_flow_rate'],
                        total_pressure_drop_pa=pressure_drop_result['total_system_pressure_drop_pa'],
                        inlet_pressure_pa=101325.0,
                        inlet_temperature_c=input_data.temperature_c,
                        blower_efficiency_override=blower_efficiency_override,
                        motor_efficiency=motor_efficiency
                    )

                    # Add aftercooling heat duty if available
                    if 'aftercooling_heat_duty_kw' in blower_result and blower_result['aftercooling_heat_duty_kw'] > 0:
                        aftercooling_kw = blower_result['aftercooling_heat_duty_kw']
                    else:
                        aftercooling_kw = None

                    # Create BlowerSpecifications object
                    blower_specs = BlowerSpecifications(
                        # Pressure drop breakdown
                        packed_bed_pressure_drop_pa=pressure_drop_result['packed_bed_pressure_drop_pa'],
                        inlet_distributor_pressure_drop_pa=pressure_drop_result['inlet_distributor_pressure_drop_pa'],
                        outlet_distributor_pressure_drop_pa=pressure_drop_result['outlet_distributor_pressure_drop_pa'],
                        demister_pressure_drop_pa=pressure_drop_result['demister_pressure_drop_pa'],
                        momentum_losses_pa=pressure_drop_result['momentum_losses_pa'],
                        ductwork_silencer_pressure_drop_pa=pressure_drop_result['ductwork_silencer_pressure_drop_pa'],
                        elevation_head_pa=pressure_drop_result['elevation_head_pa'],
                        safety_factor_pa=pressure_drop_result['safety_factor_pa'],
                        total_system_pressure_drop_pa=pressure_drop_result['total_system_pressure_drop_pa'],
                        total_system_pressure_drop_inches_h2o=pressure_drop_result['total_system_pressure_drop_inches_h2o'],
                        total_system_pressure_drop_psig=pressure_drop_result['total_system_pressure_drop_psig'],

                        # Blower selection
                        blower_type=blower_result['blower_type'],
                        compression_ratio=blower_result['compression_ratio'],
                        discharge_pressure_pa=blower_result['discharge_pressure_pa'],
                        discharge_pressure_psig=blower_result['discharge_pressure_psig'],

                        # Temperatures
                        inlet_temperature_c=blower_result['inlet_temperature_c'],
                        discharge_temperature_c=blower_result['discharge_temperature_c'],

                        # Power
                        thermodynamic_model=blower_result['thermodynamic_model'],
                        shaft_power_kw=blower_result['shaft_power_kw'],
                        motor_power_kw=blower_result['motor_power_kw'],
                        motor_power_hp=blower_result['motor_power_hp'],

                        # Efficiencies
                        blower_efficiency=blower_result['blower_efficiency'],
                        motor_efficiency=blower_result['motor_efficiency'],

                        # Optional aftercooling
                        aftercooling_heat_duty_kw=aftercooling_kw
                    )

                    # Add to result
                    result.blower_specs = blower_specs

                    logger.info(
                        f"Blower sizing complete: {blower_specs.blower_type}, "
                        f"{blower_specs.motor_power_hp:.1f} hp, "
                        f"{blower_specs.total_system_pressure_drop_psig:.2f} psig"
                    )

            except Exception as e:
                logger.warning(f"Blower sizing failed: {e}. Continuing without blower specs.", exc_info=True)
                # Continue without blower specs rather than failing the entire sizing

        logger.info(
            f"Heuristic sizing complete: {result.tower_diameter_m:.1f}m dia x "
            f"{result.tower_height_m:.1f}m height, {result.removal_efficiency_percent:.2f}% removal"
        )

        # Get molecular weight for application
        molecular_weight = DEFAULT_MOLECULAR_WEIGHTS.get(
            input_data.application.upper(),
            DEFAULT_MOLECULAR_WEIGHTS["general"]
        )

        # Get PHREEQC gas phase name
        gas_phase_name = PHREEQC_GAS_PHASES.get(
            input_data.application.upper(),
            PHREEQC_GAS_PHASES["general"]
        )

        # Bundle request + result for Tier 2 consumption
        outcome = Tier1Outcome(
            request=input_data,
            result=result,
            henry_constant=henry_constant,
            molecular_weight=molecular_weight,
            gas_phase_name=gas_phase_name,
            water_chemistry=water_chemistry_data
        )

        return outcome

    except Exception as e:
        logger.error(f"Heuristic sizing failed: {e}", exc_info=True)
        raise ValueError(f"Design calculation failed: {str(e)}") from e


async def list_available_packings() -> Dict[str, Any]:
    """
    List all available packings from the catalog.

    Returns:
        Dict with list of packings and count

    Example:
        >>> result = await list_available_packings()
        >>> print(f"Found {result['count']} packings")
        >>> for p in result['packings']:
        ...     print(f"  - {p['name']} {p['nominal_size_mm']}mm")
    """
    import sys
    from pathlib import Path

    # Add parent directory to path for imports
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from utils.packing_properties import load_packing_catalog
    from tools.schemas import PackingInfo, PackingCatalogResult

    catalog = load_packing_catalog()

    packings = []
    for packing_id, props in catalog.items():
        packing_info = PackingInfo(
            packing_id=packing_id,
            name=props['name'],
            material=props['material'],
            nominal_size_mm=props['nominal_size_mm'],
            nominal_size_in=props['nominal_size_in'],
            packing_factor_m_inv=props['packing_factor_m_inv'],
            surface_area_m2_m3=props['surface_area_m2_m3'],
            void_fraction=props['void_fraction'],
            bed_density_kg_m3=props['bed_density_kg_m3']
        )
        packings.append(packing_info)

    result = PackingCatalogResult(
        packings=packings,
        count=len(packings)
    )

    return result.model_dump()
