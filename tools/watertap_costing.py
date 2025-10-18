"""
WaterTAP Economic Costing for Degasser Systems (Tier 3).

This module orchestrates all degasser equipment costing methods and provides
a unified interface that accepts Tier 1 (heuristic sizing) or Tier 2 (PHREEQC
simulation) outputs as input.

Costing Framework:
- Equipment CAPEX: Blower, tower shell, packing, internals
- Operating OPEX: Electricity, packing replacement
- Economic metrics: NPV, LCOW, payback period

Author: Claude AI
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

# Import parameter block builders
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# LAZY IMPORTS: Defer heavy Pyomo/IDAES imports until functions are called
# This reduces MCP server startup time from 30s -> <5s
_PYOMO_LOADED = False
_IDAES_LOADED = False

logger = logging.getLogger(__name__)


def _ensure_pyomo_loaded():
    """Lazy-load Pyomo and IDAES libraries only when needed."""
    global _PYOMO_LOADED, _IDAES_LOADED, ConcreteModel, Block, pyunits, register_idaes_currency_units

    if not _PYOMO_LOADED:
        logger.debug("Loading Pyomo libraries (lazy import)...")
        from pyomo.environ import ConcreteModel as _ConcreteModel, Block as _Block, units as _pyunits
        ConcreteModel = _ConcreteModel
        Block = _Block
        pyunits = _pyunits
        _PYOMO_LOADED = True

    if not _IDAES_LOADED:
        logger.debug("Loading IDAES libraries (lazy import)...")
        from idaes.core.base.costing_base import register_idaes_currency_units as _register
        register_idaes_currency_units = _register
        register_idaes_currency_units()
        _IDAES_LOADED = True

    return ConcreteModel, Block, pyunits


@dataclass
class DegasserCostingResult:
    """
    Complete economic costing results for a degasser system.

    Attributes:
        capital_costs: Dict of equipment CAPEX (USD_2025)
        operating_costs: Dict of annual OPEX (USD_2025/year)
        total_capex: Total capital expenditure
        total_annual_opex: Total annual operating expenditure
        economic_metrics: NPV, LCOW, payback, etc.
        cost_breakdown_pct: Percentage breakdown of CAPEX
        design_summary: Key design parameters from input
    """
    capital_costs: Dict[str, float]
    operating_costs: Dict[str, float]
    total_capex: float
    total_annual_opex: float
    economic_metrics: Dict[str, float]
    cost_breakdown_pct: Dict[str, float]
    design_summary: Dict[str, Any]


class MockCostingPackage:
    """
    Mock WaterTAP costing package for standalone use.

    In production, this would be a WaterTAPCostingDetailed instance,
    but for MCP tool use we create a lightweight mock with parameter blocks.
    """
    def __init__(self):
        # Ensure Pyomo is loaded
        ConcreteModel, Block, _ = _ensure_pyomo_loaded()

        # Lazy import parameter block builders
        from utils.costing_parameters import (
            build_air_blower_cost_param_block,
            build_packed_tower_shell_cost_param_block,
            build_packing_media_cost_param_block,
            build_tower_internals_cost_param_block
        )

        # Create model for parameter construction
        m = ConcreteModel()

        # Build all parameter blocks
        m.air_blower = Block()
        build_air_blower_cost_param_block(m.air_blower)
        self.air_blower = m.air_blower

        m.packed_tower_shell = Block()
        build_packed_tower_shell_cost_param_block(m.packed_tower_shell)
        self.packed_tower_shell = m.packed_tower_shell

        m.packing_media = Block()
        build_packing_media_cost_param_block(m.packing_media)
        self.packing_media = m.packing_media

        m.tower_internals = Block()
        build_tower_internals_cost_param_block(m.tower_internals)
        self.tower_internals = m.tower_internals


def calculate_economic_metrics(
    total_capex: float,
    total_annual_opex: float,
    water_flow_m3_h: float,
    economic_params: Dict[str, Any]
) -> Dict[str, float]:
    """
    Calculate economic metrics: NPV, LCOW, payback period.

    Args:
        total_capex: Total capital expenditure (USD)
        total_annual_opex: Total annual operating cost (USD/year)
        water_flow_m3_h: Water flow rate (m³/h)
        economic_params: Economic parameters (WACC, lifetime, etc.)

    Returns:
        Dictionary with NPV, LCOW, payback_years, etc.
    """
    wacc = economic_params["wacc"]
    lifetime_years = economic_params["plant_lifetime_years"]
    utilization = economic_params["utilization_factor"]

    # Annual water production (m³/year)
    hours_per_year = 8760
    annual_water_m3 = water_flow_m3_h * hours_per_year * utilization

    # Present value of OPEX stream
    # PV = OPEX * [(1 - (1+r)^-n) / r]
    if wacc > 0:
        pv_factor = (1 - (1 + wacc) ** -lifetime_years) / wacc
    else:
        pv_factor = lifetime_years

    pv_opex = total_annual_opex * pv_factor

    # Net Present Value (negative = cost)
    npv = -(total_capex + pv_opex)

    # Levelized Cost of Water (LCOW)
    # LCOW = (CAPEX * CRF + OPEX) / Annual Water Production
    # CRF = Capital Recovery Factor = r(1+r)^n / [(1+r)^n - 1]
    if wacc > 0:
        crf = wacc * (1 + wacc) ** lifetime_years / ((1 + wacc) ** lifetime_years - 1)
    else:
        crf = 1 / lifetime_years

    lcow_usd_per_m3 = (total_capex * crf + total_annual_opex) / annual_water_m3

    # Simple payback period (years)
    # Assumes no OPEX savings (pure cost, no revenue)
    # For water treatment, payback is often based on avoided costs
    # Here we calculate if OPEX were eliminated (best case)
    if total_annual_opex > 0:
        payback_years = total_capex / total_annual_opex
    else:
        payback_years = float('inf')

    # Annualized total cost
    annualized_total_cost = total_capex * crf + total_annual_opex

    return {
        "npv_usd": npv,
        "lcow_usd_per_m3": lcow_usd_per_m3,
        "lcow_usd_per_1000gal": lcow_usd_per_m3 * 3.78541,  # Convert to $/1000 gal
        "payback_years": payback_years,
        "annualized_total_cost_usd_per_year": annualized_total_cost,
        "capital_recovery_factor": crf,
        "present_value_opex_usd": pv_opex,
        "annual_water_production_m3": annual_water_m3
    }


def cost_degasser_system(
    tier1_outcome=None,
    tier2_result: Optional[Dict[str, Any]] = None,
    application: str = "CO2",
    packing_type: str = "plastic_pall",
    economic_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Cost a complete degasser system using Tier 1 or Tier 2 design outputs.

    This function accepts the output from heuristic_sizing (Tier 1) or
    staged_column_simulation (Tier 2) and calculates complete economic costing.

    Args:
        tier1_outcome: Tier1Outcome dataclass from heuristic_sizing
        tier2_result: Optional Tier 2 simulation results dict
        application: Application type (CO2, H2S, VOC)
        packing_type: Packing material (plastic_pall, ceramic_raschig, etc.)
        economic_params: Economic parameters override

    Returns:
        DegasserCostingResult as dictionary

    Example:
        >>> # After running heuristic_sizing:
        >>> tier1_outcome = await heuristic_sizing(...)
        >>> costing = cost_degasser_system(
        ...     tier1_outcome=tier1_outcome,
        ...     application="CO2",
        ...     packing_type="plastic_pall"
        ... )
        >>> print(f"Total CAPEX: ${costing['total_capex']:,.0f}")
        >>> print(f"LCOW: ${costing['economic_metrics']['lcow_usd_per_m3']:.3f}/m³")
    """

    # Lazy import heavy dependencies only when costing is actually called
    ConcreteModel, Block, _ = _ensure_pyomo_loaded()

    from utils.degasser_costing_methods import (
        cost_air_blower,
        cost_packed_tower_shell,
        cost_packing_media,
        cost_tower_internals
    )

    from utils.economic_defaults import get_default_economic_params

    # Get economic parameters
    if economic_params is None:
        economic_params = get_default_economic_params(application)

    # Extract design parameters from Tier 1 or Tier 2
    if tier2_result is not None:
        # Use Tier 2 (more accurate)
        logger.info("Using Tier 2 simulation results for costing")
        tower_volume = 3.14159 * (tier1_outcome.result.tower_diameter_m/2)**2 * tier2_result["tower_height_m"]
        design = {
            "water_flow_m3_h": tier1_outcome.request.water_flow_rate_m3_h,
            "air_flow_m3_h": tier1_outcome.request.air_water_ratio * tier1_outcome.request.water_flow_rate_m3_h,
            "tower_diameter_m": tier1_outcome.result.tower_diameter_m,
            "tower_height_m": tier2_result["tower_height_m"],
            "tower_volume_m3": tower_volume,
            "packing_volume_m3": tower_volume * 0.80,
            "blower_power_kw": tier1_outcome.result.blower_specs.motor_power_kw if tier1_outcome.result.blower_specs else 15.0,
            "packing_name": tier1_outcome.result.packing_name,
            "source": "tier2"
        }
    elif tier1_outcome is not None:
        # Use Tier 1
        logger.info("Using Tier 1 heuristic sizing for costing")
        tower_volume = 3.14159 * (tier1_outcome.result.tower_diameter_m/2)**2 * tier1_outcome.result.tower_height_m
        design = {
            "water_flow_m3_h": tier1_outcome.request.water_flow_rate_m3_h,
            "air_flow_m3_h": tier1_outcome.request.air_water_ratio * tier1_outcome.request.water_flow_rate_m3_h,
            "tower_diameter_m": tier1_outcome.result.tower_diameter_m,
            "tower_height_m": tier1_outcome.result.tower_height_m,
            "tower_volume_m3": tower_volume,
            "packing_volume_m3": tower_volume * 0.80,  # 80% packing
            "blower_power_kw": tier1_outcome.result.blower_specs.motor_power_kw if tier1_outcome.result.blower_specs else 15.0,
            "packing_name": tier1_outcome.result.packing_name,
            "source": "tier1"
        }
    else:
        raise ValueError("Either tier1_outcome or tier2_result must be provided")

    # Create Pyomo model for costing
    m = ConcreteModel()
    m.fs = Block()

    # Create mock costing package
    m.fs.costing = MockCostingPackage()

    # Create unit blocks for each equipment piece
    m.fs.blower = Block()
    m.fs.blower.costing = Block()

    m.fs.tower = Block()
    m.fs.tower.costing = Block()

    m.fs.packing = Block()
    m.fs.packing.costing = Block()

    m.fs.internals = Block()
    m.fs.internals.costing = Block()

    # Apply costing methods
    logger.info("Applying costing methods...")

    cost_air_blower(
        blk=m.fs.blower,
        air_flow_rate_m3_h=design["air_flow_m3_h"],
        blower_power_kw=design["blower_power_kw"],
        costing_package=m.fs.costing
    )

    cost_packed_tower_shell(
        blk=m.fs.tower,
        tower_volume_m3=design["tower_volume_m3"],
        costing_package=m.fs.costing
    )

    cost_packing_media(
        blk=m.fs.packing,
        packing_volume_m3=design["packing_volume_m3"],
        packing_type=packing_type,
        costing_package=m.fs.costing
    )

    cost_tower_internals(
        blk=m.fs.internals,
        tower_diameter_m=design["tower_diameter_m"],
        costing_package=m.fs.costing
    )

    # Extract costs
    capital_costs = {
        "air_blower_system": m.fs.blower.costing.capital_cost(),
        "packed_tower_shell": m.fs.tower.costing.capital_cost(),
        "packing_media": m.fs.packing.costing.capital_cost(),
        "tower_internals": m.fs.internals.costing.capital_cost()
    }

    operating_costs = {
        "blower_electricity": m.fs.blower.costing.fixed_operating_cost(),
        "packing_replacement": m.fs.packing.costing.fixed_operating_cost()
    }

    total_capex = sum(capital_costs.values())
    total_annual_opex = sum(operating_costs.values())

    # Calculate cost breakdown percentages
    cost_breakdown_pct = {
        key: (value / total_capex * 100) for key, value in capital_costs.items()
    }

    # Calculate economic metrics
    economic_metrics = calculate_economic_metrics(
        total_capex=total_capex,
        total_annual_opex=total_annual_opex,
        water_flow_m3_h=design["water_flow_m3_h"],
        economic_params=economic_params
    )

    # Create result object
    result = DegasserCostingResult(
        capital_costs=capital_costs,
        operating_costs=operating_costs,
        total_capex=total_capex,
        total_annual_opex=total_annual_opex,
        economic_metrics=economic_metrics,
        cost_breakdown_pct=cost_breakdown_pct,
        design_summary=design
    )

    logger.info(f"Costing complete: Total CAPEX ${total_capex:,.0f}, Annual OPEX ${total_annual_opex:,.0f}/year")
    logger.info(f"LCOW: ${economic_metrics['lcow_usd_per_m3']:.3f}/m³ (${economic_metrics['lcow_usd_per_1000gal']:.2f}/1000 gal)")

    return asdict(result)


# Async wrapper for MCP tool
async def cost_degasser_system_async(
    tier1_outcome=None,
    tier2_result: Optional[Dict[str, Any]] = None,
    application: str = "CO2",
    packing_type: str = "plastic_pall",
    economic_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Async wrapper for cost_degasser_system for MCP tool compatibility.

    Args:
        tier1_outcome: Tier1Outcome dataclass from heuristic_sizing
        tier2_result: Optional Tier 2 simulation results dict
        application: Application type (CO2, H2S, VOC)
        packing_type: Packing material type
        economic_params: Economic parameters override

    Returns:
        DegasserCostingResult as dictionary
    """
    return cost_degasser_system(
        tier1_outcome=tier1_outcome,
        tier2_result=tier2_result,
        application=application,
        packing_type=packing_type,
        economic_params=economic_params
    )
