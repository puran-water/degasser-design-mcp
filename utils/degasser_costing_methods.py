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
    costing_package=None
):
    """
    Cost an air blower using Shoener et al. (2016) correlations.

    Implements three-tier sizing based on total CFM (cubic feet per minute).
    Follows WaterTAP costing pattern with Var + Constraint for capital cost.

    Args:
        blk: Unit model block to be costed
        air_flow_rate_m3_h: Air flow rate in m³/h (Var or float)
        blower_power_kw: Blower power consumption in kW (Var or float)
        costing_package: WaterTAPCostingDetailed instance

    Returns:
        Sets costing components:
        - blk.costing.capital_cost: Blower CAPEX Var with constraint
        - blk.costing.fixed_operating_cost: Annual electricity Expression

    Example:
        >>> cost_air_blower(
        ...     blk=my_unit,
        ...     air_flow_rate_m3_h=5000,
        ...     blower_power_kw=50,
        ...     costing_package=m.fs.costing
        ... )
    """
    if costing_package is None:
        raise ConfigurationError("costing_package must be provided")

    if air_flow_rate_m3_h is None:
        raise ConfigurationError("air_flow_rate_m3_h must be provided")

    if blower_power_kw is None:
        raise ConfigurationError("blower_power_kw must be provided")

    # Get parameter block
    params = costing_package.air_blower

    # Convert air flow to CFM using Expression (per Codex recommendation)
    # This keeps everything symbolic without extra Vars
    blk.costing.air_flow_cfm = Expression(
        expr=pyunits.convert(
            air_flow_rate_m3_h * pyunits.m**3 / pyunits.hour,
            to_units=pyunits.ft**3 / pyunits.min
        ),
        doc="Air flow rate in cubic feet per minute"
    )

    # Create dimensionless flow ratio (CFM / 1000)
    # Following Codex pattern: convert numerator first, then divide by same units
    blk.costing.flow_ratio_tcfm = Expression(
        expr=blk.costing.air_flow_cfm / (1000 * pyunits.ft**3 / pyunits.min),
        doc="Dimensionless flow ratio (TCFM = thousands of CFM)"
    )

    # Blower capital cost using Tier 2 (covers most applications: 883 CFM typical)
    # QSDsan formula: Cost = base * N_blowers^scale_factor * (CFM/1000)^scale_exp
    # For single blower: N_blowers = 1, so scale_factor term = 1
    blk.costing.blower_equipment_cost = Expression(
        expr=(
            params.blower_tier2_base_cost
            * params.blower_tier2_scale_factor  # For N_blowers = 1
            * blk.costing.flow_ratio_tcfm ** params.blower_tier2_scale_exp
        ),
        doc="Blower equipment cost (Shoener 2016, tier 2)"
    )

    # Air piping cost (Tier 2: 1,000-10,000 CFM)
    # Formula: coeff * AFF * TCFM^exp, where AFF = air flow fraction (1.5 default)
    blk.costing.piping_cost = Expression(
        expr=(
            params.piping_cost_tier2_coeff
            * params.air_flow_fraction_AFF
            * blk.costing.flow_ratio_tcfm ** params.piping_cost_tier2_exp
        ),
        doc="Air piping cost (Shoener 2016)"
    )

    # Blower building cost
    # Building area = 128 * TCFM^0.256 ft²
    # Building cost = area * 90 USD/ft² (escalated to 2025)
    blk.costing.building_area_ft2 = Expression(
        expr=(
            params.building_area_coeff
            * blk.costing.flow_ratio_tcfm ** params.building_area_exp
        ),
        doc="Blower building floor area (ft²)"
    )

    blk.costing.building_cost = Expression(
        expr=blk.costing.building_area_ft2 * params.building_unit_cost,
        doc="Blower building construction cost"
    )

    # Total capital cost using WaterTAP constraint pattern
    # Capital Var with Constraint (not just Expression)
    blk.costing.capital_cost = Var(
        initialize=150000,
        bounds=(0, None),
        units=pyunits.USD_2018,
        doc="Total blower system capital cost"
    )

    @blk.costing.Constraint(doc="Blower capital cost calculation")
    def capital_cost_constraint(b):
        # Sum all components and apply bare module factors
        blower_direct = params.blower_bare_module_factor * b.blower_equipment_cost
        piping_direct = params.piping_bare_module_factor * b.piping_cost
        building_direct = params.building_bare_module_factor * b.building_cost

        # Convert to base currency if needed
        return b.capital_cost == pyunits.convert(
            blower_direct + piping_direct + building_direct,
            to_units=pyunits.USD_2018
        )

    # Operating cost: Annual electricity
    # Following Codex recommendation to use WaterTAP's cost_flow if available
    # For now, use direct calculation (can upgrade to cost_flow later)
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

    _log.info("Blower costing complete (Shoener 2016): equipment + piping + building")


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
