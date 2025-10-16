"""
Henry's Law Constants Module

Query henrys_law.db for temperature-dependent Henry's constants.
Following Codex recommendation: use numeric columns, avoid HTML parsing.

Database schema (from exploration):
- species: id, iupac, formula, trivial, casrn, inchikey, subcat_id
- henry: id, Hominus (TEXT/HTML), mindHR (TEXT/HTML), htype, species_id, literature_id
- Numeric columns should exist: Hcc, dHcc, Temp, etc.

Reference: henrys-law.org, makingglitches/Henryslaw SQLite database
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import math

logger = logging.getLogger(__name__)

# Database path
DB_DIR = Path(__file__).parent.parent / "databases"
HENRYS_DB = DB_DIR / "henrys_law.db"


def get_database_schema() -> Dict[str, Any]:
    """
    Inspect henrys_law.db schema to find numeric columns.

    Returns dict with table structures and column types.
    """
    if not HENRYS_DB.exists():
        logger.error(f"Henry's law database not found: {HENRYS_DB}")
        return {}

    conn = sqlite3.connect(HENRYS_DB)
    cursor = conn.cursor()

    schema = {}

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        # Get column info for each table
        cursor.execute(f"PRAGMA table_info({table});")
        columns = cursor.fetchall()

        schema[table] = {
            'columns': [(col[1], col[2]) for col in columns],  # (name, type)
            'column_names': [col[1] for col in columns]
        }

    conn.close()

    return schema


def query_henry_by_cas(
    cas_number: str,
    temperature_c: float = 25.0,
    henry_type: str = 'cc'
) -> Optional[Dict[str, Any]]:
    """
    Query Henry's constant for a compound by CAS number.

    Args:
        cas_number: CAS registry number (e.g., "79-01-6" for TCE)
        temperature_c: Temperature in Celsius (default: 25°C)
        henry_type: Type of Henry's constant:
            - 'cc': dimensionless Cgas/Caq (concentration/concentration)
            - 'cp': Cgas/Pgas (concentration/pressure)
            - 'L': Solubility constant
            - 'M': mol/(L·atm)
            - 'V': atm·m³/mol

    Returns:
        Dict with:
        - henry_constant: H value at reference temperature
        - henry_enthalpy: ΔH for temperature correction (J/mol)
        - temperature_ref: Reference temperature (K)
        - henry_type: Type of constant
        - formula: Chemical formula
        - name: Compound name
        Or None if not found
    """
    if not HENRYS_DB.exists():
        logger.error(f"Henry's law database not found: {HENRYS_DB}")
        return None

    conn = sqlite3.connect(HENRYS_DB)
    cursor = conn.cursor()

    try:
        # First, check schema for available columns
        # Following Codex: look for numeric columns (Hcc, dHcc, etc.)
        cursor.execute("PRAGMA table_info(henry);")
        henry_columns = [row[1] for row in cursor.fetchall()]

        logger.debug(f"Henry table columns: {henry_columns}")

        # Query species by CAS number
        cursor.execute("""
            SELECT id, iupac, formula, trivial, casrn
            FROM species
            WHERE casrn = ?
        """, (cas_number,))

        species_row = cursor.fetchone()

        if not species_row:
            logger.warning(f"No species found for CAS {cas_number}")
            return None

        species_id, iupac_name, formula, trivial_name, casrn = species_row

        # Query Henry's data for this species
        # Try to use numeric columns if they exist
        # Otherwise fall back to HTML parsing

        # Check if numeric columns exist
        has_numeric = 'Hcc' in henry_columns or 'H' in henry_columns

        if has_numeric:
            # Use numeric columns (preferred)
            query = """
                SELECT h.*, s.formula, s.iupac
                FROM henry h
                JOIN species s ON h.species_id = s.id
                WHERE s.id = ? AND h.htype = ?
                LIMIT 1
            """
        else:
            # Fall back to TEXT columns
            query = """
                SELECT h.Hominus, h.mindHR, h.htype, s.formula, s.iupac
                FROM henry h
                JOIN species s ON h.species_id = s.id
                WHERE s.id = ? AND h.htype = ?
                LIMIT 1
            """

        cursor.execute(query, (species_id, henry_type))
        henry_row = cursor.fetchone()

        if not henry_row:
            logger.warning(f"No Henry's data found for CAS {cas_number}, type {henry_type}")
            return None

        # Parse the result
        # For now, return placeholder data until we understand the schema better
        # TODO: Parse numeric columns or HTML strings based on what's available

        logger.info(f"Found Henry's data for {iupac_name} ({cas_number})")
        logger.debug(f"  Columns: {henry_columns}")
        logger.debug(f"  Data: {henry_row}")

        # Return basic structure
        result = {
            'cas_number': cas_number,
            'formula': formula,
            'name': trivial_name or iupac_name,
            'henry_type': henry_type,
            'henry_constant': None,  # TODO: Parse from row
            'henry_enthalpy': None,  # TODO: Parse from row
            'temperature_ref': 298.15,  # Assume 25°C
            'data_available': True,
            'raw_data': str(henry_row)[:200]  # First 200 chars for debugging
        }

        return result

    except sqlite3.Error as e:
        logger.error(f"SQLite error querying Henry's data: {e}")
        return None

    finally:
        conn.close()


def calculate_henry_at_temperature(
    henry_ref: float,
    temp_ref: float,
    temp_target: float,
    enthalpy: float
) -> float:
    """
    Calculate Henry's constant at target temperature using van't Hoff equation.

    H(T) = H(T_ref) * exp[ ΔH/R * (1/T_ref - 1/T) ]

    Args:
        henry_ref: Henry's constant at reference temperature (dimensionless)
        temp_ref: Reference temperature (K)
        temp_target: Target temperature (K)
        enthalpy: Enthalpy of dissolution ΔH (J/mol)

    Returns:
        Henry's constant at target temperature
    """
    R = 8.314  # J/(mol·K)

    # Van't Hoff equation
    ln_H_ratio = (enthalpy / R) * (1.0 / temp_ref - 1.0 / temp_target)
    H_target = henry_ref * math.exp(ln_H_ratio)

    return H_target


def get_voc_henry_constant(
    compound_name: str,
    temperature_c: float = 25.0
) -> Optional[Dict[str, Any]]:
    """
    Get Henry's constant for a VOC from voc_properties.json or henrys_law.db.

    Args:
        compound_name: Common name (e.g., "TCE") or CAS number
        temperature_c: Temperature in Celsius

    Returns:
        Dict with Henry's constant and metadata, or None if not found
    """
    import json

    # First, check voc_properties.json
    voc_props_file = DB_DIR / "voc_properties.json"

    if voc_props_file.exists():
        with open(voc_props_file, 'r') as f:
            voc_db = json.load(f)

        # Search by CAS or by common name
        for cas, props in voc_db.items():
            if (compound_name == cas or
                compound_name.upper() in [n.upper() for n in props.get('common_names', [])]):

                # Found in VOC database
                H_25C = props.get('henry_constant_25C')
                delta_H = props.get('henry_enthalpy')

                if H_25C is None:
                    logger.warning(f"No Henry's constant for {compound_name} in VOC database")
                    continue

                # Calculate at target temperature if enthalpy available
                if delta_H and temperature_c != 25.0:
                    T_ref = 298.15  # 25°C
                    T_target = temperature_c + 273.15
                    H_target = calculate_henry_at_temperature(H_25C, T_ref, T_target, delta_H)
                else:
                    H_target = H_25C

                return {
                    'cas_number': cas,
                    'name': props.get('name'),
                    'formula': props.get('formula'),
                    'henry_constant': H_target,
                    'henry_constant_25C': H_25C,
                    'henry_enthalpy': delta_H,
                    'temperature': temperature_c,
                    'henry_type': 'cc',  # dimensionless Cgas/Caq
                    'source': 'voc_properties.json'
                }

    # If not found in VOC database, try henrys_law.db
    # Assume compound_name might be a CAS number
    if '-' in compound_name:  # CAS numbers have dashes
        result = query_henry_by_cas(compound_name, temperature_c)
        if result:
            result['source'] = 'henrys_law.db'
            return result

    logger.warning(f"No Henry's constant found for {compound_name}")
    return None


if __name__ == "__main__":
    # Test the module
    logging.basicConfig(level=logging.DEBUG)

    print("=== Henry's Law Constants Module Test ===\n")

    # 1. Get database schema
    print("1. Database schema:")
    schema = get_database_schema()
    if 'henry' in schema:
        print(f"   Henry table columns: {schema['henry']['column_names']}")
    print()

    # 2. Query TCE from voc_properties.json
    print("2. Query TCE from VOC database:")
    tce_data = get_voc_henry_constant("TCE", temperature_c=25.0)
    if tce_data:
        print(f"   Found: {tce_data['name']}")
        print(f"   H (25°C): {tce_data['henry_constant']}")
        print(f"   ΔH: {tce_data['henry_enthalpy']} J/mol")
        print(f"   Source: {tce_data['source']}")
    print()

    # 3. Test temperature correction
    print("3. Temperature correction test:")
    if tce_data:
        tce_15C = get_voc_henry_constant("TCE", temperature_c=15.0)
        tce_35C = get_voc_henry_constant("TCE", temperature_c=35.0)
        print(f"   H (15°C): {tce_15C['henry_constant']:.2f}")
        print(f"   H (25°C): {tce_data['henry_constant']:.2f}")
        print(f"   H (35°C): {tce_35C['henry_constant']:.2f}")
    print()

    # 4. Query by CAS number from henrys_law.db
    print("4. Query TCE by CAS from henrys_law.db:")
    tce_cas = query_henry_by_cas("79-01-6", henry_type='L')
    if tce_cas:
        print(f"   Found: {tce_cas['name']}")
        print(f"   Data: {tce_cas.get('raw_data', 'N/A')}")
