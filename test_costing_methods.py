"""
Test degasser costing methods with mock Pyomo blocks.

This script validates the four costing methods work correctly
without requiring a full WaterTAP flowsheet.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pyomo.environ import ConcreteModel, Block, Var, Param, units as pyunits
from idaes.core.base.costing_base import register_idaes_currency_units

# Register IDAES currency units (USD_1990, USD_2018, etc.)
register_idaes_currency_units()
from utils.costing_parameters import (
    build_air_blower_cost_param_block,
    build_packed_tower_shell_cost_param_block,
    build_packing_media_cost_param_block,
    build_tower_internals_cost_param_block
)
from utils.degasser_costing_methods import (
    cost_air_blower,
    cost_packed_tower_shell,
    cost_packing_media,
    cost_tower_internals
)


class MockCostingPackage:
    """Mock costing package with parameter blocks."""
    def __init__(self):
        # Create a temporary model for parameter construction
        m = ConcreteModel()

        # Create parameter blocks on model
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


def test_air_blower_costing():
    """Test air blower costing method."""
    print("\n" + "="*80)
    print("TEST 1: Air Blower Costing (Shoener et al. 2016)")
    print("="*80)

    # Create mock model
    m = ConcreteModel()
    m.fs = Block()
    m.fs.costing = MockCostingPackage()

    # Create mock unit
    m.fs.blower = Block()
    m.fs.blower.costing = Block()

    # Test parameters (typical CO2 stripping at 50 m³/h water)
    air_flow_m3_h = 1500  # 30:1 air-to-water ratio
    blower_power_kw = 15  # Typical for 1500 m³/h air

    print(f"\nInput Parameters:")
    print(f"  Air flow rate: {air_flow_m3_h} m³/h")
    print(f"  Air flow rate: {air_flow_m3_h * 0.5886:.0f} CFM")
    print(f"  Blower power: {blower_power_kw} kW")

    try:
        # Apply costing method
        cost_air_blower(
            blk=m.fs.blower,
            air_flow_rate_m3_h=air_flow_m3_h,
            blower_power_kw=blower_power_kw,
            costing_package=m.fs.costing
        )

        # Check results
        cfm = m.fs.blower.costing.air_flow_cfm()
        blower_equip = m.fs.blower.costing.blower_equipment_cost()
        piping_cost = m.fs.blower.costing.piping_cost()
        building_cost = m.fs.blower.costing.building_cost()
        total_capex = m.fs.blower.costing.capital_cost.value  # Var, use .value
        annual_opex = m.fs.blower.costing.fixed_operating_cost()

        print(f"\nCosting Results:")
        print(f"  Air flow: {cfm:.0f} CFM")
        print(f"  Blower equipment: ${blower_equip:,.0f}")
        print(f"  Air piping cost: ${piping_cost:,.0f}")
        print(f"  Building cost: ${building_cost:,.0f}")
        print(f"  Total CAPEX: ${total_capex:,.0f}")
        print(f"  Annual electricity: ${annual_opex:,.0f}/year")

        # Sanity checks
        assert 50000 < total_capex < 300000, "Blower CAPEX out of reasonable range"
        assert 5000 < annual_opex < 50000, "Annual OPEX out of reasonable range"

        print(f"\n[PASS] Air blower costing method works correctly!")
        return True

    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_packed_tower_shell_costing():
    """Test packed tower shell costing method."""
    print("\n" + "="*80)
    print("TEST 2: Packed Tower Shell Costing (Tang 1984)")
    print("="*80)

    # Create mock model
    m = ConcreteModel()
    m.fs = Block()
    m.fs.costing = MockCostingPackage()

    # Create mock unit
    m.fs.tower = Block()
    m.fs.tower.costing = Block()

    # Test parameters (2.5m diameter × 4m height)
    tower_volume_m3 = 3.14159 * (2.5/2)**2 * 4  # ~19.6 m³

    print(f"\nInput Parameters:")
    print(f"  Tower volume: {tower_volume_m3:.1f} m³")
    print(f"  (Assuming 2.5m diameter × 4m height)")

    try:
        # Apply costing method
        cost_packed_tower_shell(
            blk=m.fs.tower,
            tower_volume_m3=tower_volume_m3,
            costing_package=m.fs.costing
        )

        # Check results
        shell_cost = m.fs.tower.costing.shell_cost()
        foundation_cost = m.fs.tower.costing.foundation_cost()
        total_capex = m.fs.tower.costing.capital_cost()

        print(f"\nCosting Results:")
        print(f"  Shell cost (Tang 1984): ${shell_cost:,.0f}")
        print(f"  Foundation cost (15%): ${foundation_cost:,.0f}")
        print(f"  Total CAPEX: ${total_capex:,.0f}")

        # Sanity checks
        assert 10000 < total_capex < 100000, "Tower shell CAPEX out of range"
        assert abs(foundation_cost / shell_cost - 0.15) < 0.01, "Foundation not 15%"

        print(f"\n[PASS] PASS: Packed tower shell costing works correctly!")
        return True

    except Exception as e:
        print(f"\n[FAIL] FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_packing_media_costing():
    """Test packing media costing method."""
    print("\n" + "="*80)
    print("TEST 3: Packing Media Costing (EPA WBS 2015)")
    print("="*80)

    # Create mock model
    m = ConcreteModel()
    m.fs = Block()
    m.fs.costing = MockCostingPackage()

    # Create mock unit
    m.fs.packing = Block()
    m.fs.packing.costing = Block()

    # Test parameters (80% of tower volume)
    packing_volume_m3 = 19.6 * 0.80  # ~15.7 m³

    print(f"\nInput Parameters:")
    print(f"  Packing volume: {packing_volume_m3:.1f} m³")
    print(f"  Packing type: plastic_pall")

    try:
        # Apply costing method
        cost_packing_media(
            blk=m.fs.packing,
            packing_volume_m3=packing_volume_m3,
            packing_type="plastic_pall",
            costing_package=m.fs.costing
        )

        # Check results
        initial_cost = m.fs.packing.costing.capital_cost()
        annual_replacement = m.fs.packing.costing.fixed_operating_cost()

        print(f"\nCosting Results:")
        print(f"  Initial packing purchase: ${initial_cost:,.0f}")
        print(f"  Annual replacement (5%): ${annual_replacement:,.0f}/year")

        # Sanity checks
        assert 1000 < initial_cost < 50000, "Packing CAPEX out of range"
        assert abs(annual_replacement / initial_cost - 0.05) < 0.01, "Replacement not 5%"

        print(f"\n[PASS] PASS: Packing media costing works correctly!")
        return True

    except Exception as e:
        print(f"\n[FAIL] FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tower_internals_costing():
    """Test tower internals costing method."""
    print("\n" + "="*80)
    print("TEST 4: Tower Internals Costing (EPA WBS 2015)")
    print("="*80)

    # Create mock model
    m = ConcreteModel()
    m.fs = Block()
    m.fs.costing = MockCostingPackage()

    # Create mock unit
    m.fs.internals = Block()
    m.fs.internals.costing = Block()

    # Test parameters
    tower_diameter_m = 2.5

    print(f"\nInput Parameters:")
    print(f"  Tower diameter: {tower_diameter_m} m")
    print(f"  Cross-sectional area: {3.14159 * (tower_diameter_m/2)**2:.2f} m²")

    try:
        # Apply costing method
        cost_tower_internals(
            blk=m.fs.internals,
            tower_diameter_m=tower_diameter_m,
            costing_package=m.fs.costing
        )

        # Check results
        distributor = m.fs.internals.costing.distributor_cost()
        demister = m.fs.internals.costing.demister_cost()
        support_grid = m.fs.internals.costing.support_grid_cost()
        total_capex = m.fs.internals.costing.capital_cost()

        print(f"\nCosting Results:")
        print(f"  Liquid distributor: ${distributor:,.0f}")
        print(f"  Demister: ${demister:,.0f}")
        print(f"  Support grid: ${support_grid:,.0f}")
        print(f"  Total internals CAPEX: ${total_capex:,.0f}")

        # Sanity checks
        assert 1000 < total_capex < 20000, "Internals CAPEX out of range"
        assert distributor > 0, "Distributor cost must be positive"
        assert demister > 0, "Demister cost must be positive"

        print(f"\n[PASS] PASS: Tower internals costing works correctly!")
        return True

    except Exception as e:
        print(f"\n[FAIL] FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_complete_degasser_system():
    """Test complete degasser system costing."""
    print("\n" + "="*80)
    print("TEST 5: Complete Degasser System Costing")
    print("="*80)

    print("\nScenario: CO2 Stripping System")
    print("  Water flow: 50 m³/h")
    print("  Air-to-water ratio: 30:1")
    print("  Tower: 2.5m diameter × 4m height")

    # Create mock model
    m = ConcreteModel()
    m.fs = Block()
    m.fs.costing = MockCostingPackage()

    # Create all units
    m.fs.blower = Block()
    m.fs.blower.costing = Block()

    m.fs.tower = Block()
    m.fs.tower.costing = Block()

    m.fs.packing = Block()
    m.fs.packing.costing = Block()

    m.fs.internals = Block()
    m.fs.internals.costing = Block()

    # System parameters
    water_flow_m3_h = 50
    air_to_water = 30
    air_flow_m3_h = water_flow_m3_h * air_to_water
    tower_diameter_m = 2.5
    tower_height_m = 4.0
    tower_volume_m3 = 3.14159 * (tower_diameter_m/2)**2 * tower_height_m
    packing_volume_m3 = tower_volume_m3 * 0.80
    blower_power_kw = 15

    try:
        # Cost all components
        cost_air_blower(
            m.fs.blower,
            air_flow_rate_m3_h=air_flow_m3_h,
            blower_power_kw=blower_power_kw,
            costing_package=m.fs.costing
        )

        cost_packed_tower_shell(
            m.fs.tower,
            tower_volume_m3=tower_volume_m3,
            costing_package=m.fs.costing
        )

        cost_packing_media(
            m.fs.packing,
            packing_volume_m3=packing_volume_m3,
            packing_type="plastic_pall",
            costing_package=m.fs.costing
        )

        cost_tower_internals(
            m.fs.internals,
            tower_diameter_m=tower_diameter_m,
            costing_package=m.fs.costing
        )

        # Aggregate costs
        total_capex = (
            m.fs.blower.costing.capital_cost()
            + m.fs.tower.costing.capital_cost()
            + m.fs.packing.costing.capital_cost()
            + m.fs.internals.costing.capital_cost()
        )

        annual_opex = (
            m.fs.blower.costing.fixed_operating_cost()
            + m.fs.packing.costing.fixed_operating_cost()
        )

        print(f"\n" + "-"*80)
        print("CAPITAL COSTS (CAPEX):")
        print("-"*80)
        print(f"  Air blower system:     ${m.fs.blower.costing.capital_cost():>10,.0f}")
        print(f"  Packed tower shell:    ${m.fs.tower.costing.capital_cost():>10,.0f}")
        print(f"  Packing media:         ${m.fs.packing.costing.capital_cost():>10,.0f}")
        print(f"  Tower internals:       ${m.fs.internals.costing.capital_cost():>10,.0f}")
        print(f"  " + "-"*50)
        print(f"  TOTAL CAPEX:           ${total_capex:>10,.0f}")

        print(f"\n" + "-"*80)
        print("OPERATING COSTS (OPEX):")
        print("-"*80)
        print(f"  Blower electricity:    ${m.fs.blower.costing.fixed_operating_cost():>10,.0f}/year")
        print(f"  Packing replacement:   ${m.fs.packing.costing.fixed_operating_cost():>10,.0f}/year")
        print(f"  " + "-"*50)
        print(f"  TOTAL ANNUAL OPEX:     ${annual_opex:>10,.0f}/year")

        # Cost breakdown percentages
        print(f"\n" + "-"*80)
        print("CAPEX BREAKDOWN:")
        print("-"*80)
        blower_pct = m.fs.blower.costing.capital_cost() / total_capex * 100
        tower_pct = m.fs.tower.costing.capital_cost() / total_capex * 100
        packing_pct = m.fs.packing.costing.capital_cost() / total_capex * 100
        internals_pct = m.fs.internals.costing.capital_cost() / total_capex * 100

        print(f"  Air blower system:     {blower_pct:>5.1f}%")
        print(f"  Packed tower shell:    {tower_pct:>5.1f}%")
        print(f"  Packing media:         {packing_pct:>5.1f}%")
        print(f"  Tower internals:       {internals_pct:>5.1f}%")

        # Sanity checks
        assert 100000 < total_capex < 500000, "Total CAPEX out of range"
        assert 5000 < annual_opex < 50000, "Annual OPEX out of range"
        assert blower_pct > 40, "Blower should be >40% of CAPEX"

        print(f"\n[PASS] PASS: Complete system costing works correctly!")
        return True

    except Exception as e:
        print(f"\n[FAIL] FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTING DEGASSER COSTING METHODS")
    print("="*80)

    results = []

    # Run all tests
    results.append(("Air Blower", test_air_blower_costing()))
    results.append(("Tower Shell", test_packed_tower_shell_costing()))
    results.append(("Packing Media", test_packing_media_costing()))
    results.append(("Tower Internals", test_tower_internals_costing()))
    results.append(("Complete System", test_complete_degasser_system()))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for name, passed in results:
        status = "[PASS] PASS" if passed else "[FAIL] FAIL"
        print(f"  {status}: {name}")

    all_passed = all(r[1] for r in results)

    if all_passed:
        print("\n" + "="*80)
        print("[PASS] ALL TESTS PASSED - Costing methods ready for integration!")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("[FAIL] SOME TESTS FAILED - Review errors above")
        print("="*80)
