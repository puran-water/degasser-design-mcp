"""
Debug phreeqpython solution units.
"""

from phreeqpython import PhreeqPython

pp = PhreeqPython()

# Load TCE phase
voc_definitions = """
SOLUTION_MASTER_SPECIES
    Tce     Tce     0   131.388   131.388

SOLUTION_SPECIES
    Tce = Tce
        log_k 0.0
        -gamma 1.0 0.0

END
"""

pp.ip.run_string(voc_definitions)

print("Testing solution units...")
print("=" * 60)

# Test: 10 mg/L TCE
C_mg_L = 10.0
MW = 131.388

# Method 1: mol/kg directly
C_molal_1 = C_mg_L / MW / 1000.0
print(f"\nMethod 1: Direct molal")
print(f"  C_mg_L = {C_mg_L} mg/L")
print(f"  C_molal = {C_molal_1:.6e} mol/kg")

sol1 = pp.add_solution({
    'pH': 7.0,
    'temp': 25.0,
    'Tce': C_molal_1
})

print(f"  Solution total('Tce', 'mol'): {sol1.total('Tce', units='mol'):.6e} mol/kg")
print(f"  Solution total('Tce', 'mmol'): {sol1.total('Tce', units='mmol'):.6e} mmol/kg")
print(f"  Back to mg/L: {sol1.total('Tce', units='mol') * MW * 1000:.3f} mg/L")

# Method 2: mmol/L
C_mmol_L = C_mg_L / MW
print(f"\nMethod 2: Using mmol/L")
print(f"  C_mg_L = {C_mg_L} mg/L")
print(f"  C_mmol_L = {C_mmol_L:.6e} mmol/L")

sol2 = pp.add_solution({
    'pH': 7.0,
    'temp': 25.0,
    'units': 'mmol/kgw',
    'Tce': C_mmol_L
})

print(f"  Solution total('Tce', 'mol'): {sol2.total('Tce', units='mol'):.6e} mol/kg")
print(f"  Solution total('Tce', 'mmol'): {sol2.total('Tce', units='mmol'):.6e} mmol/kg")
print(f"  Back to mg/L: {sol2.total('Tce', units='mol') * MW * 1000:.3f} mg/L")

# Method 3: Try mol/L
C_mol_L = C_mg_L / MW / 1000.0
print(f"\nMethod 3: Using mol/L (assuming units='mol/L')")
print(f"  C_mg_L = {C_mg_L} mg/L")
print(f"  C_mol_L = {C_mol_L:.6e} mol/L")

sol3 = pp.add_solution({
    'pH': 7.0,
    'temp': 25.0,
    'units': 'mol/L',
    'Tce': C_mol_L
})

print(f"  Solution total('Tce', 'mol'): {sol3.total('Tce', units='mol'):.6e} mol/kg")
print(f"  Solution total('Tce', 'mmol'): {sol3.total('Tce', units='mmol'):.6e} mmol/kg")
print(f"  Back to mg/L: {sol3.total('Tce', units='mol') * MW * 1000:.3f} mg/L")

# Clean up
sol1.forget()
sol2.forget()
sol3.forget()

print("\n" + "=" * 60)
print("Key finding: Need to check units when adding solution!")