"""
Debug single equilibrium stage to understand gas phase issue.
"""

from phreeqpython import PhreeqPython
from chemicals.critical import Tc, Pc
from chemicals.acentric import omega

# Initialize PhreeqPython
pp = PhreeqPython()

# Load TCE phase
Tc_TCE = Tc("79-01-6")
Pc_TCE = Pc("79-01-6") / 101325
omega_TCE = omega("79-01-6")

voc_definitions = f"""
SOLUTION_MASTER_SPECIES
    Tce     Tce     0   131.388   131.388

SOLUTION_SPECIES
    Tce = Tce
        log_k 0.0
        -gamma 1.0 0.0

PHASES
    TCE(g)
        Tce = Tce
        -log_k   -2.322559
        -T_c     {Tc_TCE}
        -P_c     {Pc_TCE:.2f}
        -Omega   {omega_TCE}

END
"""

pp.ip.run_string(voc_definitions)

print("Single equilibrium stage test")
print("=" * 60)

# Test conditions
C_in_mg_L = 10.0
MW = 131.388
T = 25.0
air_water_ratio = 30.0

# Convert to molal
C_molal = C_in_mg_L / MW / 1000.0

print(f"\nInput conditions:")
print(f"  C_in: {C_in_mg_L} mg/L = {C_molal:.6e} mol/kg")
print(f"  Air/Water ratio: {air_water_ratio} L gas / L water")
print(f"  Temperature: {T}°C")

# Create solution
sol = pp.add_solution({
    'pH': 7.0,
    'temp': T,
    'Tce': C_molal
})

print(f"\nSolution before equilibration:")
print(f"  TCE: {sol.total('Tce', units='mol'):.6e} mol/kg")

# Calculate gas moles
R = 0.08206
T_K = T + 273.15
gas_volume_L = air_water_ratio
total_moles = (1.0 * gas_volume_L) / (R * T_K)

print(f"\nGas phase setup:")
print(f"  Volume: {gas_volume_L} L")
print(f"  Total moles at 1 atm: {total_moles:.3f} mol")

# Create clean air gas phase
n_nitrogen = total_moles
n_tce_initial = 1e-12 * total_moles  # Tiny amount for numerical stability

gas = pp.add_gas(
    components={
        "N2(g)": n_nitrogen,
        "TCE(g)": n_tce_initial
    },
    pressure=1.0,
    volume=gas_volume_L,
    fixed_volume=True,
    fixed_pressure=False
)

print(f"\nGas before equilibration:")
print(f"  Pressure: {gas.pressure:.3f} atm")
print(f"  Volume: {gas.volume:.1f} L")
print(f"  Total moles: {gas.total_moles:.3f} mol")
print(f"  Components: {gas.components}")

# Equilibrate
print(f"\n>>> Equilibrating...")
sol.interact(gas)

print(f"\nSolution after equilibration:")
C_out_mol = sol.total('Tce', units='mol')
C_out_mg_L = C_out_mol * MW * 1000.0
print(f"  TCE: {C_out_mol:.6e} mol/kg = {C_out_mg_L:.3f} mg/L")
print(f"  Stripped from liquid: {C_in_mg_L - C_out_mg_L:.3f} mg/L")

print(f"\nGas after equilibration:")
print(f"  Pressure: {gas.pressure:.3f} atm")
print(f"  Volume: {gas.volume:.1f} L")
print(f"  Total moles: {gas.total_moles:.3f} mol")
print(f"  Components: {gas.components}")

# Get TCE in gas
n_tce_final = gas.components.get('TCE(g)', 0.0)
y_tce = n_tce_final / gas.total_moles if gas.total_moles > 0 else 0.0

print(f"\nGas composition:")
print(f"  N2 moles: {gas.components.get('N2(g)', 0.0):.3f}")
print(f"  TCE moles: {n_tce_final:.6e}")
print(f"  TCE mole fraction: {y_tce:.6e}")

# Mass balance check
print(f"\n" + "=" * 60)
print("Mass balance:")

# TCE in liquid initially
mass_initial_mg = C_in_mg_L * 1.0  # 1 L water

# TCE in liquid finally
mass_final_liquid_mg = C_out_mg_L * 1.0  # 1 L water

# TCE in gas finally
mass_final_gas_mg = n_tce_final * MW * 1000.0  # mol * g/mol * mg/g

print(f"  Initial (liquid): {mass_initial_mg:.3f} mg")
print(f"  Final (liquid): {mass_final_liquid_mg:.3f} mg")
print(f"  Final (gas): {mass_final_gas_mg:.3f} mg")
print(f"  Total final: {mass_final_liquid_mg + mass_final_gas_mg:.3f} mg")
print(f"  Mass balance error: {abs(mass_initial_mg - (mass_final_liquid_mg + mass_final_gas_mg))/mass_initial_mg * 100:.1f}%")

# Expected from Henry's law
print(f"\n" + "=" * 60)
print("Henry's law check:")
H = 8.59
C_eq_mol_L = C_out_mg_L / (MW * 1000)
y_expected = H * C_eq_mol_L * R * T_K
print(f"  C_eq: {C_out_mg_L:.3f} mg/L")
print(f"  y_expected from Henry's law: {y_expected:.6e}")
print(f"  y_actual: {y_tce:.6e}")
if y_expected > 0:
    print(f"  Ratio: {y_tce/y_expected:.3f}")

# Clean up
sol.forget()
try:
    gas.forget()
except:
    pass