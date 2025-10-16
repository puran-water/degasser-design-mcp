"""
Debug staged column simulation to understand why gas isn't picking up contaminant.
"""

import numpy as np
from tools.simulation_sizing import get_phreeqc_instance, equilibrium_stage
from tools.heuristic_sizing import heuristic_sizing
from tools.schemas import HeuristicSizingInput
import asyncio

async def main():
    print("Testing staged column with detailed debugging...")
    print("=" * 70)

    # Test case: TCE stripping
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

    # Run Tier 1 to get outcome
    outcome = await heuristic_sizing(**inputs.model_dump())
    pp = get_phreeqc_instance()

    print(f"\nTest conditions:")
    print(f"  Water flow: {inputs.water_flow_rate_m3_h} m³/h")
    print(f"  C_inlet: {inputs.inlet_concentration_mg_L} mg/L")
    print(f"  C_outlet target: {inputs.outlet_concentration_mg_L} mg/L")
    print(f"  Air/Water ratio: {inputs.air_water_ratio}")
    print(f"  Temperature: {inputs.temperature_c}°C")
    print(f"  Henry constant: {inputs.henry_constant_25C}")

    # Test a few individual stages
    print("\n" + "=" * 70)
    print("Testing individual equilibrium stages:")
    print("=" * 70)

    # Stage 1: Liquid with contaminant meets clean air
    print("\nStage 1: 10 mg/L liquid meets clean air (A/W=30)")
    C_out_1, y_out_1, pH_out_1 = equilibrium_stage(
        pp,
        C_liq_in_mg_L=10.0,
        y_gas_in_frac=0.0,  # Clean air
        pH_guess=7.0,
        temperature_c=25.0,
        gas_phase_name='TCE(g)',
        aqueous_species_name='Tce',
        molecular_weight=131.388,
        air_water_ratio=30.0
    )

    print(f"  Input:  C_liq=10.00 mg/L, y_gas=0.0000")
    print(f"  Output: C_liq={C_out_1:.2f} mg/L, y_gas={y_out_1:.6f}")
    print(f"  Stripping: {10.0 - C_out_1:.2f} mg/L removed from liquid")

    # Expected from Henry's law
    H = 8.59
    R = 0.08206
    T = 298.15
    C_mol_L_expected = C_out_1 / (131.388 * 1000)
    y_expected = H * C_mol_L_expected * R * T
    print(f"  Henry's law check: y_expected={y_expected:.6f}, ratio={y_out_1/y_expected if y_expected > 0 else 0:.3f}")

    # Stage 2: Test with contaminated gas
    print("\nStage 2: 5 mg/L liquid meets contaminated air (y=0.001)")
    C_out_2, y_out_2, pH_out_2 = equilibrium_stage(
        pp,
        C_liq_in_mg_L=5.0,
        y_gas_in_frac=0.001,  # Contaminated air
        pH_guess=7.0,
        temperature_c=25.0,
        gas_phase_name='TCE(g)',
        aqueous_species_name='Tce',
        molecular_weight=131.388,
        air_water_ratio=30.0
    )

    print(f"  Input:  C_liq=5.00 mg/L, y_gas=0.001000")
    print(f"  Output: C_liq={C_out_2:.2f} mg/L, y_gas={y_out_2:.6f}")

    # Test counter-current for 3 stages
    print("\n" + "=" * 70)
    print("Testing 3-stage counter-current:")
    print("=" * 70)

    N_stages = 3
    C_liq = np.zeros(N_stages)
    y_gas = np.zeros(N_stages)

    # Initialize
    C_liq[:] = [10.0, 6.0, 2.0]  # Initial guess
    y_gas[:] = [0.002, 0.001, 0.0]  # Initial guess

    print("\nInitial profiles:")
    print(f"  C_liq: {C_liq}")
    print(f"  y_gas: {y_gas}")

    # Run 3 iterations
    for iter in range(3):
        print(f"\nIteration {iter+1}:")
        C_liq_old = C_liq.copy()

        # March through stages (bottom to top)
        for i in range(N_stages):
            # Liquid from below
            C_in = 10.0 if i == 0 else C_liq[i-1]

            # Gas from above (counter-current!)
            y_in = 0.0 if i == N_stages-1 else y_gas[i+1]

            # Equilibrate
            C_out, y_out, _ = equilibrium_stage(
                pp,
                C_liq_in_mg_L=C_in,
                y_gas_in_frac=y_in,
                pH_guess=7.0,
                temperature_c=25.0,
                gas_phase_name='TCE(g)',
                aqueous_species_name='Tce',
                molecular_weight=131.388,
                air_water_ratio=30.0
            )

            print(f"  Stage {i}: C_in={C_in:.2f}, y_in={y_in:.6f} -> C_out={C_out:.2f}, y_out={y_out:.6f}")

            C_liq[i] = C_out
            y_gas[i] = y_out

        print(f"  Updated C_liq: {[f'{c:.2f}' for c in C_liq]}")
        print(f"  Updated y_gas: {[f'{y:.6f}' for y in y_gas]}")

    # Calculate mass flows
    print("\n" + "=" * 70)
    print("Mass balance for 3-stage system:")
    print("=" * 70)

    water_flow_L_h = 100.0 * 1000  # m³/h to L/h
    air_flow_m3_h = water_flow_L_h * 30.0 / 1000  # A/W=30, convert L to m³

    mass_in = water_flow_L_h * 10.0  # mg/h
    mass_out_water = water_flow_L_h * C_liq[-1]  # mg/h

    # Gas phase mass
    R_m3 = 8.2057366e-5  # m³·atm/(mol·K)
    V_molar = R_m3 * 298.15  # m³/mol at 25°C, 1 atm
    total_mol_h = air_flow_m3_h / V_molar  # mol/h

    # Contaminant moles in gas
    y_out = y_gas[0]  # Gas leaving at bottom
    y_in = 0.0  # Clean air entering at top
    mass_stripped = (y_out - y_in) * total_mol_h * 131.388 * 1000  # mg/h

    print(f"\nFlows:")
    print(f"  Water: {water_flow_L_h:.0f} L/h")
    print(f"  Air: {air_flow_m3_h:.1f} m³/h ({total_mol_h:.0f} mol/h)")

    print(f"\nMass balance:")
    print(f"  IN:  {mass_in:.0f} mg/h")
    print(f"  OUT (water): {mass_out_water:.0f} mg/h")
    print(f"  OUT (gas):   {mass_stripped:.0f} mg/h")
    print(f"  Total OUT:   {mass_out_water + mass_stripped:.0f} mg/h")
    print(f"  Error: {abs(mass_in - (mass_out_water + mass_stripped))/mass_in * 100:.1f}%")

    print("\n" + "=" * 70)
    print("Analysis:")
    print("  - Gas phase y_gas values should be ~0.002-0.008 for proper stripping")
    print("  - Current y_gas values are showing contaminant pickup")
    print("  - Need to verify gas volume and molar calculations")

if __name__ == "__main__":
    asyncio.run(main())