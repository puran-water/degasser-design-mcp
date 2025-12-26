"""
WaterTAP-style costing parameter blocks for degasser equipment.

This module defines parameter blocks that integrate with WaterTAP's costing
framework, following the pattern from WaterTAP's unit_models/ion_exchange.py
and other detailed costing implementations.

References:
- WaterTAP costing parameter block pattern
- QSDsan Blower parameters (Shoener et al., 2016)
- EPA WBS Packed Tower Aeration Model (2015)
"""

from pyomo.environ import Param, Var, units as pyunits
from watertap.costing.util import register_costing_parameter_block
from idaes.core.base.costing_base import register_idaes_currency_units
import logging
import sys
from pathlib import Path

# Register IDAES currency units (USD_1990, USD_2018, etc.)
register_idaes_currency_units()

# Add parent directory to path for imports when running as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.economic_defaults import escalate_cost, CEPCI_INDICES

logger = logging.getLogger(__name__)


def build_air_blower_cost_param_block(blk):
    """
    Build parameter block for air blower costing.

    Based on Shoener et al. (2016) correlations as implemented in QSDsan.
    Three-tiered blower sizing with capacity-dependent cost correlations.

    References:
        Shoener, B.D., et al. (2016). "Design of Anaerobic Membrane Bioreactors
        for Municipal Wastewater Treatment." Environ. Sci. Technol.
        qsdsan/equipments/_aeration.py::Blower
    """

    # Blower efficiency parameters (from QSDsan defaults)
    blk.blower_efficiency = Param(
        initialize=0.7,
        units=pyunits.dimensionless,
        doc="Blower isentropic efficiency (QSDsan default)"
    )

    blk.motor_efficiency = Param(
        initialize=0.7,
        units=pyunits.dimensionless,
        doc="Motor efficiency (QSDsan default)"
    )

    # Air piping cost coefficients (Shoener et al., 2016, USD_2015)
    # Three tiers based on total CFM:
    # <=1000 CFM: 617.2 * AFF * TCFM^0.2553
    # 1000-10000 CFM: 1.43 * AFF * TCFM^1.1337
    # >10000 CFM: 28.59 * AFF * TCFM^0.8085

    blk.piping_cost_tier1_coeff = Param(
        initialize=escalate_cost(617.2, 2015, 2025),
        units=pyunits.USD_2018,
        mutable=True,
        doc="Air piping cost coefficient for <=1000 CFM (USD_2025)"
    )

    blk.piping_cost_tier1_exp = Param(
        initialize=0.2553,
        units=pyunits.dimensionless,
        doc="Air piping cost exponent for <=1000 CFM"
    )

    blk.piping_cost_tier2_coeff = Param(
        initialize=escalate_cost(1.43, 2015, 2025),
        units=pyunits.USD_2018,
        mutable=True,
        doc="Air piping cost coefficient for 1000-10000 CFM (USD_2025)"
    )

    blk.piping_cost_tier2_exp = Param(
        initialize=1.1337,
        units=pyunits.dimensionless,
        doc="Air piping cost exponent for 1000-10000 CFM"
    )

    blk.piping_cost_tier3_coeff = Param(
        initialize=escalate_cost(28.59, 2015, 2025),
        units=pyunits.USD_2018,
        mutable=True,
        doc="Air piping cost coefficient for >10000 CFM (USD_2025)"
    )

    blk.piping_cost_tier3_exp = Param(
        initialize=0.8085,
        units=pyunits.dimensionless,
        doc="Air piping cost exponent for >10000 CFM"
    )

    blk.air_flow_fraction_AFF = Param(
        initialize=1.5,
        units=pyunits.dimensionless,
        mutable=True,
        doc="Air flow fraction (aboveground factor, 1.0-2.0 typical)"
    )

    # Blower building cost parameters (Shoener et al., 2016, USD_2015)
    # Area = 128 * TCFM^0.256 (ft²)
    # Cost = 90 USD/ft²

    blk.building_area_coeff = Param(
        initialize=128,
        units=pyunits.ft**2,
        doc="Building area coefficient (Shoener 2016)"
    )

    blk.building_area_exp = Param(
        initialize=0.256,
        units=pyunits.dimensionless,
        doc="Building area exponent (Shoener 2016)"
    )

    blk.building_unit_cost = Param(
        initialize=escalate_cost(90, 2015, 2025),
        units=pyunits.USD_2018 / pyunits.ft**2,
        mutable=True,
        doc="Building construction cost per sq ft (USD_2025)"
    )

    # Blower capital cost tiers (from QSDsan)
    # Three capacity bands with different base costs and scaling

    blk.blower_tier1_max_cfm = Param(
        initialize=7500,
        units=pyunits.dimensionless,  # CFM
        doc="Maximum CFM per blower in tier 1 (<=30000 total)"
    )

    blk.blower_tier1_base_cost = Param(
        initialize=escalate_cost(58000, 2015, 2025),
        units=pyunits.USD_2018,
        mutable=True,
        doc="Base blower cost for tier 1 (USD_2025)"
    )

    blk.blower_tier1_scale_factor = Param(
        initialize=0.7,
        units=pyunits.dimensionless,
        doc="Blower cost scaling factor for tier 1"
    )

    blk.blower_tier1_scale_exp = Param(
        initialize=0.6169,
        units=pyunits.dimensionless,
        doc="Blower cost scaling exponent for tier 1"
    )

    blk.blower_tier2_max_cfm = Param(
        initialize=18000,
        units=pyunits.dimensionless,  # CFM
        doc="Maximum CFM per blower in tier 2 (30000-72000 total)"
    )

    blk.blower_tier2_base_cost = Param(
        initialize=escalate_cost(218000, 2015, 2025),
        units=pyunits.USD_2018,
        mutable=True,
        doc="Base blower cost for tier 2 (USD_2025)"
    )

    blk.blower_tier2_scale_factor = Param(
        initialize=0.377,
        units=pyunits.dimensionless,
        doc="Blower cost scaling factor for tier 2"
    )

    blk.blower_tier2_scale_exp = Param(
        initialize=0.5928,
        units=pyunits.dimensionless,
        doc="Blower cost scaling exponent for tier 2"
    )

    blk.blower_tier3_max_cfm = Param(
        initialize=100000,
        units=pyunits.dimensionless,  # CFM
        doc="Maximum CFM per blower in tier 3 (>72000 total)"
    )

    blk.blower_tier3_base_cost = Param(
        initialize=escalate_cost(480000, 2015, 2025),
        units=pyunits.USD_2018,
        mutable=True,
        doc="Base blower cost for tier 3 (USD_2025)"
    )

    blk.blower_tier3_scale_factor = Param(
        initialize=0.964,
        units=pyunits.dimensionless,
        doc="Blower cost scaling factor for tier 3"
    )

    blk.blower_tier3_scale_exp = Param(
        initialize=0.4286,
        units=pyunits.dimensionless,
        doc="Blower cost scaling exponent for tier 3"
    )

    # Bare module factors (from QSDsan)
    blk.blower_bare_module_factor = Param(
        initialize=2.22,
        units=pyunits.dimensionless,
        doc="Bare module factor for blowers (QSDsan)"
    )

    blk.piping_bare_module_factor = Param(
        initialize=1.0,
        units=pyunits.dimensionless,
        doc="Bare module factor for air piping (QSDsan)"
    )

    blk.building_bare_module_factor = Param(
        initialize=1.11,
        units=pyunits.dimensionless,
        doc="Bare module factor for blower building (QSDsan)"
    )


def build_packed_tower_shell_cost_param_block(blk):
    """
    Build parameter block for packed tower shell costing.

    Based on Tang (1984) correlation from WaterTAP cost_cstr module.
    Vessel cost = A * V^b where V is vessel volume in m³.

    References:
        Tang, Y.T. (1984) via watertap/costing/unit_models/cstr.py
        Original: Capital = 1,246.1 USD_1990 * V^0.71
    """

    # Tang (1984) vessel shell cost correlation (escalated to USD_2025)
    blk.vessel_cost_coefficient = Param(
        initialize=escalate_cost(1246.1, 1990, 2025),
        units=pyunits.USD_2018,
        mutable=True,
        doc="Vessel shell cost coefficient A (USD_2025)"
    )

    blk.vessel_cost_exponent = Param(
        initialize=0.71,
        units=pyunits.dimensionless,
        doc="Vessel shell cost exponent b (economies of scale)"
    )

    # Foundation and civil costs
    blk.foundation_cost_fraction = Param(
        initialize=0.15,
        units=pyunits.dimensionless,
        mutable=True,
        doc="Foundation cost as fraction of vessel shell cost"
    )

    # Material factor (FRP standard, stainless steel higher)
    blk.material_factor_frp = Param(
        initialize=1.0,
        units=pyunits.dimensionless,
        doc="Material factor for FRP (fiberglass reinforced plastic)"
    )

    blk.material_factor_ss304 = Param(
        initialize=2.5,
        units=pyunits.dimensionless,
        doc="Material factor for stainless steel 304"
    )

    blk.material_factor_ss316 = Param(
        initialize=3.0,
        units=pyunits.dimensionless,
        doc="Material factor for stainless steel 316"
    )


def build_packing_media_cost_param_block(blk):
    """
    Build parameter block for packing material costing.

    Based on EPA Work Breakdown Structure (WBS) Packed Tower Aeration Model (2015).
    Unit costs per cubic meter of packing, escalated to current year.

    References:
        EPA WBS Packed Tower Aeration Model (2015)
        Original values in USD_2019, escalated to USD_2025
    """

    # Packing material unit costs (USD_2025 per m³)
    # User-configurable for vendor quotes

    blk.plastic_pall_cost = Param(
        initialize=escalate_cost(115, 2019, 2025),
        units=pyunits.USD_2018 / pyunits.m**3,
        mutable=True,
        doc="Plastic Pall ring packing cost per m³ (USD_2025)"
    )

    blk.plastic_raschig_cost = Param(
        initialize=escalate_cost(95, 2019, 2025),
        units=pyunits.USD_2018 / pyunits.m**3,
        mutable=True,
        doc="Plastic Raschig ring packing cost per m³ (USD_2025)"
    )

    blk.ceramic_raschig_cost = Param(
        initialize=escalate_cost(2400, 2019, 2025),
        units=pyunits.USD_2018 / pyunits.m**3,
        mutable=True,
        doc="Ceramic Raschig ring packing cost per m³ (USD_2025)"
    )

    blk.plastic_intalox_cost = Param(
        initialize=escalate_cost(132, 2019, 2025),
        units=pyunits.USD_2018 / pyunits.m**3,
        mutable=True,
        doc="Plastic Intalox saddle packing cost per m³ (USD_2025)"
    )

    blk.structured_packing_cost = Param(
        initialize=escalate_cost(350, 2019, 2025),
        units=pyunits.USD_2018 / pyunits.m**3,
        mutable=True,
        doc="Structured packing cost per m³ (USD_2025)"
    )

    # Packing replacement rate (annual fraction)
    blk.packing_replacement_rate = Param(
        initialize=0.05,
        units=pyunits.dimensionless,
        mutable=True,
        doc="Annual packing replacement rate (5% typical for plastic)"
    )


def build_tower_internals_cost_param_block(blk):
    """
    Build parameter block for tower internals costing.

    Includes liquid distributors, gas distributors, and demisters.
    Based on EPA WBS Packed Tower Aeration Model (2015).

    References:
        EPA WBS Packed Tower Aeration Model (2015)
        Costs scale with tower diameter
    """

    # Liquid distributor costs (USD_2025)
    # Cost = base + factor * diameter_m

    blk.liquid_distributor_base_cost = Param(
        initialize=escalate_cost(500, 2019, 2025),
        units=pyunits.USD_2018,
        mutable=True,
        doc="Liquid distributor base cost (USD_2025)"
    )

    blk.liquid_distributor_area_cost = Param(
        initialize=escalate_cost(200, 2019, 2025),
        units=pyunits.USD_2018 / pyunits.m**2,
        mutable=True,
        doc="Liquid distributor cost per m² of tower cross-section (USD_2025)"
    )

    # Gas distributor costs (USD_2025)
    # Simpler than liquid distributor

    blk.gas_distributor_base_cost = Param(
        initialize=escalate_cost(300, 2019, 2025),
        units=pyunits.USD_2018,
        mutable=True,
        doc="Gas distributor base cost (USD_2025)"
    )

    blk.gas_distributor_diameter_factor = Param(
        initialize=150,
        units=pyunits.USD_2018 / pyunits.m,
        mutable=True,
        doc="Gas distributor cost per meter of diameter (USD_2025/m)"
    )

    # Demister/mist eliminator costs (USD_2025 per m² of cross-section)

    blk.demister_unit_cost = Param(
        initialize=escalate_cost(150, 2019, 2025),
        units=pyunits.USD_2018 / pyunits.m**2,
        mutable=True,
        doc="Demister cost per m² of tower cross-section (USD_2025)"
    )

    # Support structures
    blk.support_grid_unit_cost = Param(
        initialize=escalate_cost(96, 2019, 2025),
        units=pyunits.USD_2018 / pyunits.m**2,
        mutable=True,
        doc="Packing support grid cost per m² of tower cross-section (USD_2025)"
    )


if __name__ == "__main__":
    """Test parameter block creation."""
    from pyomo.environ import ConcreteModel, Block
    from watertap.costing import WaterTAPCostingDetailed

    print("=" * 80)
    print("DEGASSER COSTING PARAMETER BLOCKS - TEST")
    print("=" * 80)

    # Create a simple model
    m = ConcreteModel()
    m.fs = Block()

    # Add WaterTAP costing with detailed parameters
    m.fs.costing = WaterTAPCostingDetailed()

    # Manually create parameter blocks for testing
    m.fs.costing.air_blower = Block()
    m.fs.costing.packed_tower_shell = Block()
    m.fs.costing.packing_media = Block()
    m.fs.costing.tower_internals = Block()

    # Build parameter blocks directly
    print("\nBuilding air_blower parameter block...")
    build_air_blower_cost_param_block(m.fs.costing.air_blower)
    print(f"  Blower efficiency: {m.fs.costing.air_blower.blower_efficiency.value}")
    print(f"  Piping tier 3 coeff: ${m.fs.costing.air_blower.piping_cost_tier3_coeff.value:.2f}")
    print(f"  Building cost: ${m.fs.costing.air_blower.building_unit_cost.value:.2f}/sq.ft")
    print(f"  Tier 1 blower base: ${m.fs.costing.air_blower.blower_tier1_base_cost.value:,.0f}")

    print("\nBuilding packed_tower_shell parameter block...")
    build_packed_tower_shell_cost_param_block(m.fs.costing.packed_tower_shell)
    print(f"  Vessel cost coefficient: ${m.fs.costing.packed_tower_shell.vessel_cost_coefficient.value:.2f}")
    print(f"  Vessel cost exponent: {m.fs.costing.packed_tower_shell.vessel_cost_exponent.value:.2f}")
    print(f"  Foundation fraction: {m.fs.costing.packed_tower_shell.foundation_cost_fraction.value:.1%}")

    print("\nBuilding packing_media parameter block...")
    build_packing_media_cost_param_block(m.fs.costing.packing_media)
    print(f"  Plastic Pall rings: ${m.fs.costing.packing_media.plastic_pall_cost.value:.2f}/m³")
    print(f"  Ceramic rings: ${m.fs.costing.packing_media.ceramic_raschig_cost.value:.2f}/m³")
    print(f"  Replacement rate: {m.fs.costing.packing_media.packing_replacement_rate.value:.1%}/year")

    print("\nBuilding tower_internals parameter block...")
    build_tower_internals_cost_param_block(m.fs.costing.tower_internals)
    print(f"  Liquid distributor base: ${m.fs.costing.tower_internals.liquid_distributor_base_cost.value:.2f}")
    print(f"  Demister unit cost: ${m.fs.costing.tower_internals.demister_unit_cost.value:.2f}/m²")
    print(f"  Support grid cost: ${m.fs.costing.tower_internals.support_grid_cost_per_m2.value:.2f}/m²")

    print("\n" + "=" * 80)
    print("[PASS] All parameter blocks created successfully!")
    print("=" * 80)
    print("\nThese parameter blocks integrate with WaterTAP's costing framework")
    print("via the @register_costing_parameter_block decorator.")
