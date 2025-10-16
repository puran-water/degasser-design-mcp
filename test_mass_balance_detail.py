"""
Detailed mass balance test to understand the 8% error.
"""

import asyncio
import numpy as np
from tools.simulation_sizing import get_phreeqc_instance, solve_counter_current_stages, validate_mass_balance
from tools.heuristic_sizing import heuristic_sizing
from tools.schemas import HeuristicSizingInput

async def main():
    print("Mass balance investigation")
    print("=" * 60)

    # Test case
    inputs = HeuristicSizingInput(
        application='VOC',
        water_flow_rate_m3_h=100.0,
        inlet_concentration_mg_L=10.0,
        outlet_concentration_mg_L=1.0,
        air_water_ratio=30.0,
        temperature_c=25.0,
        water_ph=7.0,
        henry_constant_25C=8.59
    )

    outcome = await heuristic_sizing(**inputs.model_dump())
    pp = get_phreeqc_instance()

    # Run simulation with 15 stages
    profiles = solve_counter_current_stages(
        pp,
        outcome,
        N_stages=15,
        convergence_tolerance=0.01
    )

    print(f"\nConvergence info:")
    print(f"  Converged: {profiles['converged']}")
    print(f"  Iterations: {profiles['iterations']}")

    print(f"\nConcentration profiles:")
    print(f"  Stage    C_liq (mg/L)    y_gas (frac)")
    for i in range(16):
        print(f"    {i:2d}      {profiles['C_liq'][i]:8.3f}       {profiles['y_gas'][i]:.6e}")

    # Validate mass balance
    mass_balance = validate_mass_balance(
        outcome,
        profiles['C_liq'],
        profiles['y_gas']
    )

    print(f"\nMass balance:")
    print(f"  Mass in: {mass_balance['mass_in_mg_h']:.2f} mg/h")
    print(f"  Mass out (water): {mass_balance['mass_out_water_mg_h']:.2f} mg/h")
    print(f"  Mass out (gas): {mass_balance['mass_stripped_mg_h']:.2f} mg/h")
    print(f"  Error: {mass_balance['error_fraction']:.2%}")

    # Check if we're meeting outlet target
    print(f"\nOutlet concentration:")
    print(f"  Target: {inputs.outlet_concentration_mg_L} mg/L")
    print(f"  Actual: {profiles['C_liq'][-1]:.3f} mg/L")

    # Run with tighter tolerance
    print(f"\n" + "=" * 60)
    print("Testing with tighter convergence tolerance (0.001):")

    profiles_tight = solve_counter_current_stages(
        pp,
        outcome,
        N_stages=15,
        convergence_tolerance=0.001
    )

    print(f"\nConvergence info:")
    print(f"  Converged: {profiles_tight['converged']}")
    print(f"  Iterations: {profiles_tight['iterations']}")

    # Validate mass balance
    mass_balance_tight = validate_mass_balance(
        outcome,
        profiles_tight['C_liq'],
        profiles_tight['y_gas']
    )

    print(f"\nMass balance:")
    print(f"  Mass in: {mass_balance_tight['mass_in_mg_h']:.2f} mg/h")
    print(f"  Mass out (water): {mass_balance_tight['mass_out_water_mg_h']:.2f} mg/h")
    print(f"  Mass out (gas): {mass_balance_tight['mass_stripped_mg_h']:.2f} mg/h")
    print(f"  Error: {mass_balance_tight['error_fraction']:.2%}")

    print(f"\nOutlet concentration:")
    print(f"  Target: {inputs.outlet_concentration_mg_L} mg/L")
    print(f"  Actual: {profiles_tight['C_liq'][-1]:.3f} mg/L")

if __name__ == "__main__":
    asyncio.run(main())