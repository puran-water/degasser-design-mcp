"""
Debug script to understand phreeqpython Gas object API and fix extraction issues.
"""

from phreeqpython import PhreeqPython
import numpy as np

# Initialize PhreeqPython
pp = PhreeqPython()

# Load N2 and TCE phases with critical properties
from chemicals.critical import Tc, Pc
from chemicals.acentric import omega

# TCE properties
Tc_TCE = Tc("79-01-6")  # K
Pc_TCE = Pc("79-01-6") / 101325  # Pa to atm
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

print("Testing phreeqpython Gas object API...")
print("=" * 60)

# Test 1: Create a simple gas phase
print("\n1. Create gas with N2 and TCE:")
gas = pp.add_gas(
    components={
        "N2(g)": 1.0,      # 1 mol N2
        "TCE(g)": 0.01     # 0.01 mol TCE
    },
    pressure=1.0,
    volume=25.0,
    fixed_volume=True,
    fixed_pressure=False
)

# Check available attributes
print("\nAvailable Gas attributes:")
for attr in dir(gas):
    if not attr.startswith('_'):
        print(f"  - {attr}")

# Try different ways to get gas composition
print("\n2. Gas composition BEFORE equilibration:")
print(f"   gas.pressure: {gas.pressure:.3f} atm")
print(f"   gas.volume: {gas.volume:.1f} L")

# Check if we can get components
if hasattr(gas, 'components'):
    print(f"   gas.components type: {type(gas.components)}")
    print(f"   gas.components: {gas.components}")

if hasattr(gas, 'partial_pressures'):
    print(f"   gas.partial_pressures: {gas.partial_pressures}")

if hasattr(gas, 'total_moles'):
    print(f"   gas.total_moles: {gas.total_moles}")

# Get composition using gas.gas dictionary
if hasattr(gas, 'gas'):
    print(f"\n   gas.gas dictionary:")
    for key, value in gas.gas.items():
        print(f"     {key}: {value}")

# Test 2: Equilibrate with solution and check changes
print("\n3. Creating solution with 10 mg/L TCE:")
sol = pp.add_solution({
    'pH': 7.0,
    'temp': 25.0,
    'Tce': 10.0 / 131.388 / 1000.0  # 10 mg/L as mol/kg
})

print("\n4. Equilibrating gas with solution...")
sol.interact(gas)

print("\n5. Gas composition AFTER equilibration:")
print(f"   gas.pressure: {gas.pressure:.3f} atm")
print(f"   gas.volume: {gas.volume:.1f} L")

# Check components after equilibration
if hasattr(gas, 'gas'):
    print(f"\n   gas.gas dictionary after equilibration:")
    for key, value in gas.gas.items():
        print(f"     {key}: {value}")

# Try to calculate mole fractions correctly
print("\n6. Calculating mole fractions:")
if hasattr(gas, 'gas'):
    gas_dict = gas.gas

    # Look for moles in the dictionary
    if 'N2(g)' in gas_dict and 'TCE(g)' in gas_dict:
        # These might be moles or partial pressures
        n2_value = gas_dict['N2(g)']
        tce_value = gas_dict['TCE(g)']

        print(f"   N2(g) value: {n2_value}")
        print(f"   TCE(g) value: {tce_value}")

        # If these are partial pressures, calculate moles
        R = 0.08206  # L·atm/(mol·K)
        T = 298.15  # K

        # Method 1: Assume values are moles
        total_moles_1 = n2_value + tce_value
        y_tce_1 = tce_value / total_moles_1 if total_moles_1 > 0 else 0
        print(f"\n   Method 1 (assuming moles):")
        print(f"     Total moles: {total_moles_1:.3f}")
        print(f"     y_TCE: {y_tce_1:.6f}")

        # Method 2: Assume values are partial pressures
        if gas.pressure > 0:
            y_tce_2 = tce_value / gas.pressure
            print(f"\n   Method 2 (assuming partial pressures):")
            print(f"     Total pressure: {gas.pressure:.3f} atm")
            print(f"     y_TCE: {y_tce_2:.6f}")

        # Method 3: Calculate from PV=nRT
        total_moles_3 = (gas.pressure * gas.volume) / (R * T)
        print(f"\n   Method 3 (from PV=nRT):")
        print(f"     Total moles: {total_moles_3:.3f}")

# Test what solution sees
print("\n7. Solution composition after equilibration:")
print(f"   TCE in solution: {sol.total('Tce', units='mol'):.6e} mol/kg")
print(f"   TCE in mg/L: {sol.total('Tce', units='mol') * 131.388 * 1000:.3f} mg/L")

# Clean up
sol.forget()
try:
    gas.forget()
except:
    pass

print("\n" + "=" * 60)
print("Debug complete. Key findings will inform fix.")