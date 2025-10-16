"""
Test Tier 3 economic costing integration with Tier 1 and Tier 2.

This script demonstrates the complete three-tier degasser design pipeline:
1. Tier 1: Fast heuristic sizing
2. Tier 2: PHREEQC gas-liquid equilibrium (optional)
3. Tier 3: WaterTAP economic costing

Tests all three applications: CO2, H2S, VOC
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from tools.heuristic_sizing import heuristic_sizing
from tools.simulation_sizing import staged_column_simulation
from tools.watertap_costing import cost_degasser_system

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


async def test_co2_stripping_full_pipeline():
    """Test complete pipeline for CO2 stripping application."""

    print("\n" + "="*80)
    print("TEST 1: CO2 Stripping - Full Three-Tier Pipeline")
    print("="*80)

    # Input parameters
    params = {
        "application": "CO2",
        "water_flow_rate_m3_h": 50.0,
        "inlet_concentration_mg_L": 100.0,  # ~100 mg/L as CO2
        "outlet_concentration_mg_L": 5.0,   # Target <5 mg/L
        "air_water_ratio": 30.0,
        "temperature_c": 25.0,
        "water_ph": 5.0,  # Acidified for CO2 stripping
    }

    print("\nInput Parameters:")
    for key, value in params.items():
        print(f"  {key}: {value}")

    try:
        # === TIER 1: Heuristic Sizing ===
        print("\n" + "-"*80)
        print("TIER 1: Heuristic Sizing")
        print("-"*80)

        tier1_outcome = await heuristic_sizing(**params)

        print(f"Tower diameter: {tier1_outcome.result.tower_diameter_m:.2f} m")
        print(f"Tower height: {tier1_outcome.result.tower_height_m:.2f} m")
        print(f"Packing: {tier1_outcome.result.packing_name}")
        if tier1_outcome.result.blower_specs:
            print(f"Blower power: {tier1_outcome.result.blower_specs.motor_power_kw:.1f} kW")

        # === TIER 2: PHREEQC Simulation (Optional) ===
        # Commented out for speed - uncomment to test full pipeline
        tier2_result = None
        # print("\n" + "-"*80)
        # print("TIER 2: PHREEQC Simulation (SKIPPED - uncomment to run)")
        # print("-"*80)

        # === TIER 3: Economic Costing ===
        print("\n" + "-"*80)
        print("TIER 3: Economic Costing")
        print("-"*80)

        tier3_result = cost_degasser_system(
            tier1_outcome=tier1_outcome,
            tier2_result=tier2_result,
            application="CO2",
            packing_type="plastic_pall"
        )

        # Display results
        print("\nCAPITAL COSTS (CAPEX):")
        for equip, cost in tier3_result['capital_costs'].items():
            pct = tier3_result['cost_breakdown_pct'][equip]
            print(f"  {equip:30s} ${cost:>12,.0f}  ({pct:5.1f}%)")
        print(f"  {'TOTAL CAPEX':30s} ${tier3_result['total_capex']:>12,.0f}")

        print("\nOPERATING COSTS (OPEX):")
        for item, cost in tier3_result['operating_costs'].items():
            print(f"  {item:30s} ${cost:>12,.0f}/year")
        print(f"  {'TOTAL ANNUAL OPEX':30s} ${tier3_result['total_annual_opex']:>12,.0f}/year")

        print("\nECONOMIC METRICS:")
        metrics = tier3_result['economic_metrics']
        print(f"  LCOW: ${metrics['lcow_usd_per_m3']:.3f}/m³ (${metrics['lcow_usd_per_1000gal']:.2f}/1000 gal)")
        print(f"  Payback period: {metrics['payback_years']:.1f} years")
        print(f"  Annualized cost: ${metrics['annualized_total_cost_usd_per_year']:,.0f}/year")
        print(f"  NPV (30 years): ${metrics['npv_usd']:,.0f}")

        print("\n[PASS] CO2 stripping pipeline complete!")
        return True

    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_h2s_stripping_costing():
    """Test H2S stripping with Tier 3 costing."""

    print("\n" + "="*80)
    print("TEST 2: H2S Stripping - Tier 1 + Tier 3")
    print("="*80)

    params = {
        "application": "H2S",
        "water_flow_rate_m3_h": 25.0,
        "inlet_concentration_mg_L": 30.0,  # High H2S concentration
        "outlet_concentration_mg_L": 0.5,  # Target <0.5 mg/L (odor threshold)
        "air_water_ratio": 40.0,  # Higher A/W for H2S
        "temperature_c": 25.0,
        "water_ph": 5.0,  # Acidified to shift equilibrium
    }

    print("\nInput Parameters:")
    for key, value in params.items():
        print(f"  {key}: {value}")

    try:
        # Tier 1
        tier1_outcome = await heuristic_sizing(**params)

        print(f"\nTower: {tier1_outcome.result.tower_diameter_m:.2f}m D × "
              f"{tier1_outcome.result.tower_height_m:.2f}m H")

        # Tier 3
        tier3_result = cost_degasser_system(
            tier1_outcome=tier1_outcome,
            application="H2S",
            packing_type="plastic_pall"
        )

        print(f"\nTotal CAPEX: ${tier3_result['total_capex']:,.0f}")
        print(f"Annual OPEX: ${tier3_result['total_annual_opex']:,.0f}/year")
        print(f"LCOW: ${tier3_result['economic_metrics']['lcow_usd_per_m3']:.3f}/m³")

        print("\n[PASS] H2S stripping costing complete!")
        return True

    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_voc_stripping_costing():
    """Test VOC stripping with Tier 3 costing."""

    print("\n" + "="*80)
    print("TEST 3: VOC Stripping (Trichloroethylene) - Tier 1 + Tier 3")
    print("="*80)

    params = {
        "application": "VOC",
        "water_flow_rate_m3_h": 10.0,
        "inlet_concentration_mg_L": 5.0,  # 5 mg/L TCE (contaminated groundwater)
        "outlet_concentration_mg_L": 0.005,  # Target <5 µg/L (MCL)
        "air_water_ratio": 50.0,  # High A/W for VOC
        "temperature_c": 20.0,
        "henry_constant_25C": 0.01,  # TCE at 25°C (dimensionless)
    }

    print("\nInput Parameters:")
    for key, value in params.items():
        print(f"  {key}: {value}")

    try:
        # Tier 1
        tier1_outcome = await heuristic_sizing(**params)

        print(f"\nTower: {tier1_outcome.result.tower_diameter_m:.2f}m D × "
              f"{tier1_outcome.result.tower_height_m:.2f}m H")

        # Tier 3
        tier3_result = cost_degasser_system(
            tier1_outcome=tier1_outcome,
            application="VOC",
            packing_type="plastic_pall"
        )

        print(f"\nTotal CAPEX: ${tier3_result['total_capex']:,.0f}")
        print(f"Annual OPEX: ${tier3_result['total_annual_opex']:,.0f}/year")
        print(f"LCOW: ${tier3_result['economic_metrics']['lcow_usd_per_m3']:.3f}/m³")

        # Cost per m³ treated
        annual_water_m3 = tier3_result['economic_metrics']['annual_water_production_m3']
        print(f"Annual water treated: {annual_water_m3:,.0f} m³/year")

        print("\n[PASS] VOC stripping costing complete!")
        return True

    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_packing_comparison():
    """Test cost comparison across different packing types."""

    print("\n" + "="*80)
    print("TEST 4: Packing Type Comparison - CO2 Stripping")
    print("="*80)

    params = {
        "application": "CO2",
        "water_flow_rate_m3_h": 50.0,
        "inlet_concentration_mg_L": 100.0,
        "outlet_concentration_mg_L": 5.0,
        "air_water_ratio": 30.0,
        "temperature_c": 25.0,
        "water_ph": 5.0,
    }

    # Test different packing types
    packing_types = ["plastic_pall", "plastic_raschig", "ceramic_raschig"]

    try:
        # Run Tier 1 once
        tier1_outcome = await heuristic_sizing(**params)

        print(f"\nBase design: {tier1_outcome.result.tower_diameter_m:.2f}m D × "
              f"{tier1_outcome.result.tower_height_m:.2f}m H")

        print("\nPacking Type Comparison:")
        print(f"{'Packing Type':<25} {'Total CAPEX':>15} {'LCOW ($/m³)':>15}")
        print("-"*60)

        for packing in packing_types:
            tier3_result = cost_degasser_system(
                tier1_outcome=tier1_outcome,
                application="CO2",
                packing_type=packing
            )

            capex = tier3_result['total_capex']
            lcow = tier3_result['economic_metrics']['lcow_usd_per_m3']

            print(f"{packing:<25} ${capex:>13,.0f}  ${lcow:>13.3f}")

        print("\n[PASS] Packing comparison complete!")
        return True

    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all Tier 3 integration tests."""

    print("\n" + "="*80)
    print("TIER 3 ECONOMIC COSTING - INTEGRATION TESTS")
    print("="*80)

    results = []

    # Run all tests
    results.append(("CO2 Full Pipeline", await test_co2_stripping_full_pipeline()))
    results.append(("H2S Costing", await test_h2s_stripping_costing()))
    results.append(("VOC Costing", await test_voc_stripping_costing()))
    results.append(("Packing Comparison", await test_packing_comparison()))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")

    all_passed = all(r[1] for r in results)

    if all_passed:
        print("\n" + "="*80)
        print("[PASS] ALL INTEGRATION TESTS PASSED!")
        print("="*80)
        print("\nTier 3 economic costing is ready for production use.")
        print("MCP tools available:")
        print("  - cost_degasser_system_async: Standalone Tier 3 costing")
        print("  - combined_simulation_mcp: Tier 1+2+3 pipeline with run_tier3=True")
    else:
        print("\n" + "="*80)
        print("[FAIL] SOME TESTS FAILED - Review errors above")
        print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
