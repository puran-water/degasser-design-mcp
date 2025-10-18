"""
Degasser/Stripping Tower Equipment Costing Methods.

WaterTAP-compatible costing methods for degasser equipment following
the costing framework patterns from watertap_contrib.reflo.costing.

Costing Methods:
1. cost_air_blower - Shoener et al. (2016) from QSDsan
2. cost_packed_tower_shell - Tang (1984) from WaterTAP cost_cstr
3. cost_packing_media - EPA WBS Packed Tower Aeration (2015)
4. cost_tower_internals - EPA WBS Packed Tower Aeration (2015)

References:
- Shoener, B. D., et al. (2016). Energy positive domestic wastewater treatment.
  Environ. Sci.: Processes Impacts, 18(9), 1202-1210.
- Tang, Y. T., et al. (1984). Economic Analysis of Electrochemical Equipment.
  J. Electrochem. Soc., 131(1), 115-118.
- EPA Work Breakdown Structure (WBS) Packed Tower Aeration Model v2.0 (2015)

Author: Claude AI
"""

from pyomo.environ import Var, Param, Expression, Constraint, units as pyunits
from idaes.core.base.costing_base import register_idaes_currency_units
from watertap.core.util.initialization import assert_degrees_of_freedom
from idaes.core.util.exceptions import ConfigurationError
import idaes.logger as idaeslog

# Register IDAES currency units
register_idaes_currency_units()

_log = idaeslog.getLogger(__name__)


def cost_air_blower(
    blk,
    air_flow_rate_m3_h=None,
    blower_power_kw=None,
    costing_package=None,
    material_factor=1.0
):
    """
    Cost an air blower using three-tier hybrid correlation.

    Implements intelligent tier selection based on blower size:
    - Small (< 7.5 kW): IDAES SSLW power-based (accurate for HVAC/small blowers)
    - Medium (7.5-37.5 kW): WaterTAP-Reflo ASDC flow-based
    - Large (> 37.5 kW): QSDsan Shoener CFM-based (industrial wastewater)

    Follows WaterTAP costing pattern with Var + Constraint for capital cost.

    Args:
        blk: Unit model block to be costed
        air_flow_rate_m3_h: Air flow rate in m³/h (Var or float)
        blower_power_kw: Blower power consumption in kW (Var or float)
        costing_package: WaterTAPCostingDetailed instance
        material_factor: Material construction multiplier (1.0=aluminum, 2.5=SS304, 3.0=SS316)

    Returns:
        Sets costing components:
        - blk.costing.capital_cost: Blower CAPEX Var with constraint
        - blk.costing.fixed_operating_cost: Annual electricity Expression
        - blk.costing.blower_tier: Which correlation was used (for auditing)

    Example:
        >>> cost_air_blower(
        ...     blk=my_unit,
        ...     air_flow_rate_m3_h=1500,  # 883 CFM
        ...     blower_power_kw=0.76,     # 1 HP
        ...     costing_package=m.fs.costing,
        ...     material_factor=1.0       # Aluminum
        ... )
    """
    if costing_package is None:
        raise ConfigurationError("costing_package must be provided")

    if air_flow_rate_m3_h is None:
        raise ConfigurationError("air_flow_rate_m3_h must be provided")

    if blower_power_kw is None:
        raise ConfigurationError("blower_power_kw must be provided")

    # Import three-tier correlations
    from utils.economic_defaults import (
        cost_small_blower_idaes_sslw,
        cost_medium_blower_asdc,
        cost_large_blower_qsdsan
    )

    # Get parameter block
    params = costing_package.air_blower

    # Determine which tier to use based on power
    # Thresholds chosen to avoid discontinuities and match correlation ranges
    if blower_power_kw < 7.5:  # < 10 HP
        # Tier 1: Small blowers (IDAES SSLW power-based)
        # Best for regenerative blowers, HVAC fans, small centrifugal
        blower_equipment_cost_usd = cost_small_blower_idaes_sslw(
            blower_power_kw,
            material_factor=material_factor
        )
        tier_used = "small_idaes_sslw"
        _log.info(f"Using IDAES SSLW correlation (small blower, {blower_power_kw:.2f} kW)")

    elif blower_power_kw < 37.5:  # 10-50 HP
        # Tier 2: Medium blowers (WaterTAP-Reflo ASDC flow-based)
        # Best for packaged air stripping systems, mid-scale process blowers
        blower_equipment_cost_usd = cost_medium_blower_asdc(air_flow_rate_m3_h)
        tier_used = "medium_asdc"
        _log.info(f"Using ASDC correlation (medium blower, {air_flow_rate_m3_h:.0f} m³/h)")

    else:  # > 50 HP
        # Tier 3: Large industrial blowers (QSDsan Shoener CFM-based)
        # Best for municipal wastewater, large industrial air systems
        blower_equipment_cost_usd = cost_large_blower_qsdsan(
            air_flow_rate_m3_h,
            n_blowers=1  # Single blower for now, can be parameterized later
        )
        tier_used = "large_qsdsan"
        _log.info(f"Using QSDsan Shoener correlation (large blower, {air_flow_rate_m3_h:.0f} m³/h)")

    # Store tier used for auditing/debugging
    blk.costing.blower_tier = tier_used

    # Convert to Pyomo units
    blk.costing.blower_equipment_cost = Expression(
        expr=blower_equipment_cost_usd * pyunits.USD_2018,
        doc=f"Blower equipment cost ({tier_used})"
    )

    # Air piping and building costs (scale-appropriate estimations)
    # For small/medium blowers: simplified estimates
    # For large blowers: use QSDsan Shoener correlations

    if blower_power_kw < 37.5:  # Small and medium blowers
        # Simplified piping: 10% of equipment cost
        blk.costing.piping_cost = Expression(
            expr=blower_equipment_cost_usd * 0.10 * pyunits.USD_2018,
            doc="Air piping cost (simplified for small/medium blowers)"
        )

        # Simplified building: 15% of equipment cost (or none for small HVAC units)
        if blower_power_kw < 7.5:
            # Small blowers often wall-mounted, minimal building cost
            blk.costing.building_cost = Expression(
                expr=blower_equipment_cost_usd * 0.05 * pyunits.USD_2018,
                doc="Blower housing/mounting cost (small blower)"
            )
        else:
            blk.costing.building_cost = Expression(
                expr=blower_equipment_cost_usd * 0.15 * pyunits.USD_2018,
                doc="Blower building cost (medium blower)"
            )

    else:  # Large industrial blowers use QSDsan correlations
        # Convert to CFM for QSDsan formulas
        cfm = air_flow_rate_m3_h * 35.3147 / 60
        tcfm = cfm / 1000  # Thousands of CFM

        # QSDsan piping correlation (Tier 2 for typical range)
        piping_cost_usd = (
            params.piping_cost_tier2_coeff *
            params.air_flow_fraction_AFF *
            (tcfm ** params.piping_cost_tier2_exp)
        )
        blk.costing.piping_cost = Expression(
            expr=piping_cost_usd,
            doc="Air piping cost (QSDsan Shoener 2016)"
        )

        # QSDsan building correlation
        building_area_ft2 = params.building_area_coeff * (tcfm ** params.building_area_exp)
        building_cost_usd = building_area_ft2 * params.building_unit_cost
        blk.costing.building_cost = Expression(
            expr=building_cost_usd,
            doc="Blower building cost (QSDsan Shoener 2016)"
        )

    # Total capital cost using Expression (consistent with tower, packing, internals)
    if blower_power_kw < 37.5:
        # Small/medium: correlations already include installation
        cost_expr = blk.costing.blower_equipment_cost + blk.costing.piping_cost + blk.costing.building_cost
    else:
        # Large: apply bare module factors from QSDsan
        blower_direct = params.blower_bare_module_factor * blk.costing.blower_equipment_cost
        piping_direct = params.piping_bare_module_factor * blk.costing.piping_cost
        building_direct = params.building_bare_module_factor * blk.costing.building_cost
        cost_expr = blower_direct + piping_direct + building_direct

    blk.costing.capital_cost = Expression(
        expr=cost_expr,
        doc="Total blower system capital cost (equipment + piping + building)"
    )

    # Operating cost: Annual electricity
    utilization_factor = 0.9  # 90% uptime
    hours_per_year = 8760

    blk.costing.fixed_operating_cost = Expression(
        expr=(
            pyunits.convert(blower_power_kw * pyunits.kW, to_units=pyunits.kW)
            * hours_per_year * pyunits.hour / pyunits.year
            * utilization_factor
            * 0.07 * pyunits.USD_2018 / pyunits.kWh  # Default electricity cost
        ),
        doc="Annual blower electricity cost"
    )

    _log.info(f"Blower costing complete ({tier_used}): equipment + piping + building")


def cost_packed_tower_shell(
    blk,
    tower_volume_m3=None,
    costing_package=None
):
    """
    Cost a packed tower shell using Tang (1984) correlation.

    Tang (1984) vessel shell cost correlation from WaterTAP cost_cstr:
        Capital = A * V^b
    where:
        A = 1,246.1 USD_1990 (escalated to 2025)
        b = 0.71 (economies of scale exponent)
        V = vessel volume in m³

    Also includes foundation cost (15% of shell cost).

    Args:
        blk: Unit model block to be costed
        tower_volume_m3: Tower volume in m³ (Var or float)
        costing_package: WaterTAPCostingDetailed instance

    Returns:
        Sets costing expressions:
        - blk.costing.shell_cost: Vessel shell cost only
        - blk.costing.foundation_cost: Foundation cost
        - blk.costing.capital_cost: Total shell + foundation

    Example:
        >>> cost_packed_tower_shell(
        ...     blk=my_unit,
        ...     tower_volume_m3=25.0,
        ...     costing_package=m.fs.costing
        ... )
    """
    if costing_package is None:
        raise ConfigurationError("costing_package must be provided")

    if tower_volume_m3 is None:
        raise ConfigurationError("tower_volume_m3 must be provided")

    # Get parameter block
    params = costing_package.packed_tower_shell

    # Vessel shell cost: Capital = A * V^b
    blk.costing.shell_cost = Expression(
        expr=(
            params.vessel_cost_coefficient
            * tower_volume_m3 ** params.vessel_cost_exponent
        ),
        doc="Packed tower shell cost (Tang 1984, USD_2018)"
    )

    # Foundation cost (15% of shell cost)
    blk.costing.foundation_cost = Expression(
        expr=blk.costing.shell_cost * params.foundation_cost_fraction,
        doc="Tower foundation cost (USD_2018)"
    )

    # Total capital cost
    blk.costing.capital_cost = Expression(
        expr=blk.costing.shell_cost + blk.costing.foundation_cost,
        doc="Total tower shell + foundation (USD_2018)"
    )

    _log.info(f"Packed tower shell costing complete (Tang 1984)")


def cost_packing_media(
    blk,
    packing_volume_m3=None,
    packing_type="plastic_pall",
    costing_package=None
):
    """
    Cost packing media using EPA WBS Packed Tower Aeration Model (2015).

    Packing costs per m³ (USD_2019, escalated to 2025):
    - Plastic Pall rings: 115 USD/m³
    - Ceramic Raschig rings: 2,400 USD/m³
    - Plastic Raschig rings: 180 USD/m³
    - Plastic Intalox saddles: 160 USD/m³

    Also includes annual replacement cost (5% typical for plastic).

    Args:
        blk: Unit model block to be costed
        packing_volume_m3: Packing volume in m³ (Var or float)
        packing_type: Packing material type (default "plastic_pall")
        costing_package: WaterTAPCostingDetailed instance

    Returns:
        Sets costing expressions:
        - blk.costing.capital_cost: Initial packing purchase (USD_2018)
        - blk.costing.fixed_operating_cost: Annual replacement (USD_2018/year)

    Example:
        >>> cost_packing_media(
        ...     blk=my_unit,
        ...     packing_volume_m3=20.0,
        ...     packing_type="plastic_pall",
        ...     costing_package=m.fs.costing
        ... )
    """
    if costing_package is None:
        raise ConfigurationError("costing_package must be provided")

    if packing_volume_m3 is None:
        raise ConfigurationError("packing_volume_m3 must be provided")

    # Get parameter block
    params = costing_package.packing_media

    # Select packing cost based on type
    packing_cost_map = {
        "plastic_pall": params.plastic_pall_cost,
        "ceramic_raschig": params.ceramic_raschig_cost,
        "plastic_raschig": params.plastic_raschig_cost,
        "plastic_intalox": params.plastic_intalox_cost,
    }

    if packing_type not in packing_cost_map:
        raise ConfigurationError(
            f"Unknown packing_type '{packing_type}'. "
            f"Must be one of: {list(packing_cost_map.keys())}"
        )

    unit_cost = packing_cost_map[packing_type]

    # Capital cost: Initial packing purchase
    blk.costing.capital_cost = Expression(
        expr=packing_volume_m3 * unit_cost,
        doc=f"Packing media capital cost ({packing_type}, USD_2018)"
    )

    # Operating cost: Annual replacement
    # Typically 5% per year for plastic, 2% for ceramic
    blk.costing.fixed_operating_cost = Expression(
        expr=blk.costing.capital_cost * params.packing_replacement_rate,
        doc="Annual packing replacement cost (USD_2018/year)"
    )

    _log.info(f"Packing media costing complete: {packing_type}")


def cost_tower_internals(
    blk,
    tower_diameter_m=None,
    costing_package=None
):
    """
    Cost tower internals using EPA WBS Packed Tower Aeration Model (2015).

    Includes:
    - Liquid distributor: Base cost + area-dependent cost
    - Demister (mist eliminator): 150 USD/m² of tower cross-section
    - Support grids: 96 USD/m² of tower cross-section

    Args:
        blk: Unit model block to be costed
        tower_diameter_m: Tower diameter in meters (Var or float)
        costing_package: WaterTAPCostingDetailed instance

    Returns:
        Sets costing expressions:
        - blk.costing.distributor_cost: Liquid distributor cost
        - blk.costing.demister_cost: Demister cost
        - blk.costing.support_grid_cost: Support grid cost
        - blk.costing.capital_cost: Total internals cost

    Example:
        >>> cost_tower_internals(
        ...     blk=my_unit,
        ...     tower_diameter_m=2.5,
        ...     costing_package=m.fs.costing
        ... )
    """
    if costing_package is None:
        raise ConfigurationError("costing_package must be provided")

    if tower_diameter_m is None:
        raise ConfigurationError("tower_diameter_m must be provided")

    # Get parameter block
    params = costing_package.tower_internals

    # Tower cross-sectional area
    blk.costing.tower_cross_section_m2 = Expression(
        expr=3.14159 * (tower_diameter_m / 2) ** 2,
        doc="Tower cross-sectional area (m²)"
    )

    # Liquid distributor cost
    # Base cost + area-dependent cost
    blk.costing.distributor_cost = Expression(
        expr=(
            params.liquid_distributor_base_cost
            + params.liquid_distributor_area_cost * blk.costing.tower_cross_section_m2
        ),
        doc="Liquid distributor cost (USD_2018)"
    )

    # Demister cost
    blk.costing.demister_cost = Expression(
        expr=params.demister_unit_cost * blk.costing.tower_cross_section_m2,
        doc="Demister (mist eliminator) cost (USD_2018)"
    )

    # Support grid cost
    blk.costing.support_grid_cost = Expression(
        expr=params.support_grid_unit_cost * blk.costing.tower_cross_section_m2,
        doc="Packing support grid cost (USD_2018)"
    )

    # Total capital cost
    blk.costing.capital_cost = Expression(
        expr=(
            blk.costing.distributor_cost
            + blk.costing.demister_cost
            + blk.costing.support_grid_cost
        ),
        doc="Total tower internals cost (USD_2018)"
    )

    _log.info(f"Tower internals costing complete")


# Future enhancements:
# - Add vapor_compression option for closed-loop systems
# - Add offgas_treatment for H2S/VOC applications (scrubber, GAC)
# - Add instrumentation & control costs (5-10% of equipment)
# - Add installation labor (EPA WBS factors: 30-50% of equipment)
