"""
Generate unified VOC properties database from multiple sources.

Combines:
1. value.json (VOC data from Air-stripping-column repo)
2. henrys_law.db (SQLite database from henrys-law.org)
3. Perry's Handbook data (to be added via semantic search)

Output:
- voc_properties.json: Unified database with CAS number keys
- voc_phases.dat: PHREEQC PHASES definitions for custom VOCs
"""

import json
import sqlite3
import os
from pathlib import Path

# Database paths
DB_DIR = Path(__file__).parent
VALUE_JSON = DB_DIR / "value.json"
HENRYS_DB = DB_DIR / "henrys_law.db"
VOC_PROPERTIES_JSON = DB_DIR / "voc_properties.json"
VOC_PHASES_DAT = DB_DIR / "voc_phases.dat"


def load_value_json():
    """Load VOC data from value.json."""
    with open(VALUE_JSON, 'r') as f:
        return json.load(f)


def query_henrys_law_db(compound_name=None, cas_number=None):
    """
    Query Henry's law database.

    Returns: dict with Henry's constant data including temperature dependence
    """
    if not HENRYS_DB.exists():
        print(f"Warning: Henry's law database not found at {HENRYS_DB}")
        return {}

    conn = sqlite3.connect(HENRYS_DB)
    cursor = conn.cursor()

    # Get table structure first
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Available tables: {tables}")

    # For now, return empty dict until we explore the schema
    # TODO: Implement proper query logic once schema is understood
    conn.close()
    return {}


def create_unified_voc_properties():
    """
    Create unified VOC properties database.

    Structure:
    {
        "CAS_NUMBER": {
            "name": "Trichloroethylene",
            "common_names": ["TCE", "Trichloroethene"],
            "formula": "C2HCl3",
            "molecular_weight": 131.4,  # g/mol
            "henry_constant_25C": 8.59,  # dimensionless (Cgas/Caq)
            "henry_enthalpy": 3410,  # J/mol (for temperature correction)
            "boiling_point": 87.2,  # °C
            "diffusion_volume": 93.48,  # for Fuller-Schettler-Giddings correlation
            "sources": ["value.json", "henrys_law.db", "Perry's Handbook"]
        }
    }
    """

    # Load existing data
    value_data = load_value_json()

    # Initialize unified database
    unified_db = {}

    # Process value.json entries
    # Note: value.json doesn't have CAS numbers, so we'll use compound names as keys for now
    # TODO: Add CAS number mapping

    cas_mapping = {
        "TCE": "79-01-6",  # Trichloroethylene
        "CCL4": "56-23-5"  # Carbon tetrachloride
    }

    import re

    for compound_key, data in value_data.items():
        cas = cas_mapping.get(compound_key, f"UNKNOWN_{compound_key}")

        # Clean boiling point - extract numeric value only
        boiling_point_raw = data.get("Boilling temp.", "")
        boiling_point_c = None
        if boiling_point_raw:
            # Extract just the numeric value
            bp_match = re.search(r'([\d.]+)', boiling_point_raw)
            if bp_match:
                try:
                    boiling_point_c = float(bp_match.group(1))
                except ValueError:
                    boiling_point_c = None

        unified_db[cas] = {
            "name": data.get("Contamenat ", "").strip(),
            "common_names": [compound_key],
            "formula": data.get("Chemical formula ", "").strip(),
            "molecular_weight": data.get("Molculer weight (g/mol)", None),
            "henry_constant_25C": data.get("K", None),  # Dimensionless H
            "henry_enthalpy": data.get("delta_H", None),  # J/mol
            "boiling_point_c": boiling_point_c,  # Numeric °C
            "diffusion_volume": data.get("Diffusion volume", None),
            "atomic_volume": data.get("Aatomic Volume", None),
            "sources": ["value.json"]
        }

    # TODO: Query henrys_law.db for additional compounds and temperature data
    # henrys_data = query_henrys_law_db()

    # Save unified database
    with open(VOC_PROPERTIES_JSON, 'w') as f:
        json.dump(unified_db, f, indent=2)

    print(f"Created unified VOC properties database: {VOC_PROPERTIES_JSON}")
    print(f"  - {len(unified_db)} compounds")

    return unified_db


def generate_phreeqc_phases(voc_db):
    """
    Generate PHREEQC PHASES definitions for VOCs.

    PHREEQC format:
    PHASES
      TCE(g)
      C2HCl3 = C2HCl3
      -log_k -0.066  # Calculated from Henry's constant
      -analytic A B C D E  # Temperature dependence coefficients
    END

    Note: PHREEQC equilibrium is: aq_species = gas_phase
          K = P_gas / activity_aq
          For dimensionless H (Cgas/Caq), K = H * R * T
          log_k = log10(H * R * T)

    PHREEQC -analytic format: log10(K) = A + B/T + C*log10(T) + D*T + E/T^2
    For van't Hoff: log10(K(T)) = log10(K_ref) - ΔH/(2.303*R) * (1/T - 1/T_ref)
                    which becomes: A + B/T where:
                    B = -ΔH / (2.303 * R)
                    A = log10(K_ref) - B / T_ref
    """

    import math

    phases_content = """# PHREEQC PHASES definitions for VOC stripping
# Generated from unified VOC properties database
#
# Henry's law: Cgas = H * Caq (dimensionless form)
# PHREEQC equilibrium: aq_species = gas_phase, K = P_gas / activity_aq
# For dimensionless H: K = H * R * T (where R = 0.08206 L·atm/(mol·K))
# -log_k = log10(K)
#
# Temperature dependence (van't Hoff):
# PHREEQC -analytic: log10(K) = A + B/T + C*log10(T) + D*T + E/T^2
# For van't Hoff: B = -ΔH/(2.303*R), A = log10(K_ref) - B/T_ref
#
# Sources: value.json, henrys_law.db
# Reference: phreeqc.dat CO2(g) format

PHASES
"""

    R_SI = 8.314  # J/(mol·K)
    R_atm = 0.08206  # L·atm/(mol·K) for pressure calculation
    T_ref = 298.15  # 25°C in Kelvin

    for cas, props in voc_db.items():
        formula = props.get("formula", "")
        name = props.get("common_names", [""])[0]
        H_25C = props.get("henry_constant_25C")  # dimensionless Cgas/Caq
        delta_H = props.get("henry_enthalpy")  # J/mol

        if not H_25C or not formula:
            continue

        # Calculate PHREEQC equilibrium constant
        # PHREEQC equilibrium: aq_species = gas_phase
        # K = P_gas / activity_aq = 1 / (Hcc * R * T)
        # where Hcc is dimensionless (Caq/Cgas), so our H (Cgas/Caq) = 1/Hcc
        # Therefore: K = H * R * T, but PHREEQC uses -log_k = log10(K)
        # Wait, checking phreeqc.dat format: CO2(g) uses -log_k for the value
        # So we need: -log_k <negative value> to get correct equilibrium
        K_25C = 1.0 / (H_25C * R_atm * T_ref)  # K = 1 / (H * R * T)
        log_k_25C = math.log10(K_25C)

        phases_content += f"\n  {name}(g)\n"
        phases_content += f"  {formula} = {formula}\n"
        phases_content += f"  -log_k {log_k_25C:.6f}  # From H = {H_25C} (dimensionless) at 25°C\n"

        # Add temperature dependence if enthalpy available
        if delta_H:
            # PHREEQC -analytic format: log10(K) = A + B/T + C*log10(T) + D*T + E/T^2
            # Van't Hoff: log10(K(T)) = log10(K_ref) - ΔH/(2.303*R) * (1/T - 1/T_ref)
            # Rearrange: log10(K(T)) = [log10(K_ref) + ΔH/(2.303*R*T_ref)] + [-ΔH/(2.303*R)] / T
            # So: A = log10(K_ref) + ΔH/(2.303*R*T_ref), B = -ΔH/(2.303*R)

            B = -delta_H / (2.303 * R_SI)
            A = log_k_25C - B / T_ref

            phases_content += f"  -analytic {A:.6f} {B:.6f} 0 0 0\n"
            phases_content += f"  # ΔH = {delta_H} J/mol for temperature correction\n"
            phases_content += f"  # Van't Hoff: log10(K) = {A:.6f} + {B:.6f}/T\n"

        phases_content += f"  # CAS: {cas}\n"

    phases_content += "\nEND\n"

    # Save PHREEQC phases file with UTF-8 encoding
    with open(VOC_PHASES_DAT, 'w', encoding='utf-8') as f:
        f.write(phases_content)

    print(f"Generated PHREEQC phases file: {VOC_PHASES_DAT}")

    return VOC_PHASES_DAT


def explore_henrys_db():
    """Explore Henry's law database schema."""
    if not HENRYS_DB.exists():
        print(f"Henry's law database not found at {HENRYS_DB}")
        return

    conn = sqlite3.connect(HENRYS_DB)
    cursor = conn.cursor()

    print("\n=== Henry's Law Database Schema ===\n")

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    for (table_name,) in tables:
        print(f"\nTable: {table_name}")

        # Get column info
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()

        print(f"  Columns:")
        for col in columns:
            print(f"    - {col[1]} ({col[2]})")

        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        print(f"  Rows: {count}")

        # Show sample data (first 3 rows)
        if count > 0:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
            samples = cursor.fetchall()
            print(f"  Sample data:")
            for row in samples[:3]:
                try:
                    print(f"    {row}")
                except UnicodeEncodeError:
                    print(f"    [Row with special characters - skipped for display]")

    conn.close()


if __name__ == "__main__":
    print("=== VOC Database Generation ===\n")

    # First, explore the Henry's law database schema
    print("Step 1: Exploring Henry's law database schema...")
    explore_henrys_db()

    # Create unified VOC properties database
    print("\nStep 2: Creating unified VOC properties database...")
    voc_db = create_unified_voc_properties()

    # Generate PHREEQC phases file
    print("\nStep 3: Generating PHREEQC phases file...")
    generate_phreeqc_phases(voc_db)

    print("\n=== Database Generation Complete ===")
    print(f"\nGenerated files:")
    print(f"  - {VOC_PROPERTIES_JSON}")
    print(f"  - {VOC_PHASES_DAT}")
    print(f"\nNext steps:")
    print(f"  1. Review generated files")
    print(f"  2. Add more VOC compounds from henrys_law.db")
    print(f"  3. Query Perry's Handbook for additional properties")
    print(f"  4. Implement temperature-dependent Henry's constant queries")
