"""
Water chemistry parsing and PHREEQC solution helpers.

This module mirrors the RO design MCP water chemistry schema so both
servers can share feed chemistry data seamlessly.  It provides:

- Parsing/validation of JSON strings using the same ion naming convention
  (e.g., "Na+", "Ca2+", "HCO3-").
- Charge balance diagnostics to help spot inconsistent analyses.
- Conversion to PHREEQC-ready solution dictionaries (mg/L basis) that
  preserve charge balance and can be merged with contaminant loads.

Notes:
    * PHREEQC expects elemental totals (e.g., S(6) for sulfate expressed
      as sulfur).  Mapping factors below convert ion concentrations to the
      appropriate elemental basis while keeping mg/L units.
    * Default background water chemistries provide realistic counter-ions
      when no explicit analysis is supplied (prevents artificial pH drift).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ion definitions (aligned with RO design MCP)
# ---------------------------------------------------------------------------

VALID_IONS: Dict[str, Dict[str, float]] = {
    # Cations
    "Na+": {"charge": 1, "mw": 22.99, "name": "Sodium"},
    "Ca2+": {"charge": 2, "mw": 40.08, "name": "Calcium"},
    "Mg2+": {"charge": 2, "mw": 24.31, "name": "Magnesium"},
    "K+": {"charge": 1, "mw": 39.10, "name": "Potassium"},
    "Fe2+": {"charge": 2, "mw": 55.85, "name": "Iron(II)"},
    "Fe3+": {"charge": 3, "mw": 55.85, "name": "Iron(III)"},
    "Mn2+": {"charge": 2, "mw": 54.94, "name": "Manganese"},
    "Ba2+": {"charge": 2, "mw": 137.33, "name": "Barium"},
    "Sr2+": {"charge": 2, "mw": 87.62, "name": "Strontium"},
    "NH4+": {"charge": 1, "mw": 18.04, "name": "Ammonium"},
    "H+": {"charge": 1, "mw": 1.01, "name": "Hydrogen"},

    # Anions
    "Cl-": {"charge": -1, "mw": 35.45, "name": "Chloride"},
    "SO4-2": {"charge": -2, "mw": 96.06, "name": "Sulfate"},
    "HCO3-": {"charge": -1, "mw": 61.02, "name": "Bicarbonate"},
    "CO3-2": {"charge": -2, "mw": 60.01, "name": "Carbonate"},
    "NO3-": {"charge": -1, "mw": 62.00, "name": "Nitrate"},
    "F-": {"charge": -1, "mw": 19.00, "name": "Fluoride"},
    "PO4-3": {"charge": -3, "mw": 94.97, "name": "Phosphate"},
    "SiO3-2": {"charge": -2, "mw": 76.08, "name": "Silicate"},
    "Br-": {"charge": -1, "mw": 79.90, "name": "Bromide"},
    "B(OH)4-": {"charge": -1, "mw": 78.84, "name": "Borate"},
    "OH-": {"charge": -1, "mw": 17.01, "name": "Hydroxide"},
}

# Default water chemistry templates (mg/L) shared with RO tool
DEFAULT_WATER_TEMPLATES: Dict[str, Dict[str, float]] = {
    "municipal": {
        "Na+": 50.0,
        "Ca2+": 40.0,
        "Mg2+": 10.0,
        "K+": 5.0,
        "Cl-": 60.0,
        "SO4-2": 30.0,
        "HCO3-": 120.0,
        "NO3-": 10.0,
    },
    "brackish": {
        "Na+": 1000.0,
        "Ca2+": 100.0,
        "Mg2+": 50.0,
        "K+": 20.0,
        "Cl-": 1500.0,
        "SO4-2": 200.0,
        "HCO3-": 200.0,
    },
    "seawater": {
        "Na+": 10770.0,
        "Mg2+": 1290.0,
        "Ca2+": 412.0,
        "K+": 399.0,
        "Sr2+": 7.9,
        "Cl-": 19350.0,
        "SO4-2": 2712.0,
        "HCO3-": 142.0,
        "Br-": 67.0,
        "B(OH)4-": 4.5,
        "F-": 1.3,
    },
}

# Map RO JSON ion names to PHREEQC element keywords
# Conversion factor = molecular weight of ion / elemental weight (unitless)
ION_MAPPING: Dict[str, Tuple[str, float]] = {
    # Cations
    "Na+": ("Na", 1.0),
    "Ca2+": ("Ca", 1.0),
    "Ca+2": ("Ca", 1.0),
    "Mg2+": ("Mg", 1.0),
    "Mg+2": ("Mg", 1.0),
    "K+": ("K", 1.0),
    "Fe2+": ("Fe(2)", 1.0),
    "Fe3+": ("Fe(3)", 1.0),
    "Mn2+": ("Mn", 1.0),
    "Ba2+": ("Ba", 1.0),
    "Sr2+": ("Sr", 1.0),
    "NH4+": ("N(-3)", 18.04 / 14.01),  # Express on nitrogen basis

    # Anions
    "Cl-": ("Cl", 1.0),
    "SO4-2": ("S(6)", 96.06 / 32.07),  # Sulfur basis
    "SO4^2-": ("S(6)", 96.06 / 32.07),
    "HCO3-": ("Alkalinity", 1.0),  # Treated as mg/L as HCO3-
    "CO3-2": ("C(4)", 60.01 / 12.01),  # Carbon basis
    "CO3^2-": ("C(4)", 60.01 / 12.01),
    "NO3-": ("N(5)", 62.00 / 14.01),  # Nitrogen basis
    "F-": ("F", 1.0),
    "PO4-3": ("P", 94.97 / 30.97),  # Phosphorus basis
    "Br-": ("Br", 1.0),
    "B(OH)4-": ("B", 78.84 / 10.81),  # Boron basis
    "SiO2": ("Si", 60.08 / 28.09),
    "SiO3-2": ("Si", 76.08 / 28.09),
    "H4SiO4": ("Si", 96.11 / 28.09),

    # Legacy plain-element names (for robustness)
    "Na": ("Na", 1.0),
    "Ca": ("Ca", 1.0),
    "Mg": ("Mg", 1.0),
    "K": ("K", 1.0),
    "Cl": ("Cl", 1.0),
    "SO4": ("S(6)", 96.06 / 32.07),
    "HCO3": ("Alkalinity", 1.0),
    "F": ("F", 1.0),
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WaterChemistryData:
    """
    Container for validated water chemistry inputs.

    Attributes:
        ion_composition_mg_l: User-supplied (or default) ions in mg/L.
        phreeqc_solution_mg_l: Converted dictionary ready for add_solution().
        charge_balance_percent: Charge imbalance (positive = excess cations).
        source: Source descriptor (e.g., "user", "default:municipal").
    """

    ion_composition_mg_l: Dict[str, float]
    phreeqc_solution_mg_l: Dict[str, float]
    charge_balance_percent: float
    source: str = "user"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def parse_water_chemistry_json(
    water_chemistry_json: str
) -> Dict[str, float]:
    """Parse JSON string into an ion concentration dictionary."""
    try:
        ion_dict = json.loads(water_chemistry_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON for water chemistry: {exc}") from exc

    if not isinstance(ion_dict, dict):
        raise ValueError("Water chemistry must be a JSON object of ion: concentration pairs.")

    validated: Dict[str, float] = {}
    for ion, value in ion_dict.items():
        if not isinstance(value, (int, float)):
            raise ValueError(f"Concentration for {ion} must be numeric, got {type(value).__name__}.")
        if value < 0:
            raise ValueError(f"Concentration for {ion} cannot be negative ({value}).")
        validated[ion] = float(value)

    if not validated:
        raise ValueError("Water chemistry dictionary cannot be empty.")

    return validated


def calculate_charge_balance(ion_dict: Dict[str, float]) -> float:
    """
    Calculate charge balance error (%) based on supplied ion concentrations.

    Positive values indicate excess cations, negative values indicate
    excess anions.
    """
    cation_meq = 0.0
    anion_meq = 0.0

    for ion, conc_mg_l in ion_dict.items():
        props = VALID_IONS.get(ion)
        if not props:
            continue

        meq_l = conc_mg_l / props["mw"] * abs(props["charge"])
        if props["charge"] > 0:
            cation_meq += meq_l
        else:
            anion_meq += meq_l

    total_meq = cation_meq + anion_meq
    if total_meq == 0:
        return 0.0

    return (cation_meq - anion_meq) / total_meq * 100.0


def build_phreeqc_solution(
    ion_dict_mg_l: Dict[str, float],
    *,
    units: str = "mg/L"
) -> Dict[str, float]:
    """
    Convert RO-style ion dictionary to PHREEQC solution keywords.

    Args:
        ion_dict_mg_l: Ion concentrations in mg/L using charge-tagged names.
        units: Units to declare for PHREEQC solution (default mg/L).

    Returns:
        Dictionary with keys/values ready for PhreeqPython.add_solution().
    """
    if units.lower() != "mg/l":
        raise ValueError("Currently only mg/L units are supported for PHREEQC conversion.")

    solution: Dict[str, float] = {}
    for ion, conc in ion_dict_mg_l.items():
        mapping = ION_MAPPING.get(ion)
        if mapping:
            keyword, conversion = mapping
            solution[keyword] = conc / conversion
        else:
            logger.warning(f"Unknown ion '{ion}' supplied; passing through directly.")
            solution[ion] = conc

    return solution


def get_default_water_chemistry(template: str = "municipal") -> Dict[str, float]:
    """
    Retrieve default background chemistry (mg/L).

    Args:
        template: Template key ("municipal", "brackish", "seawater").

    Returns:
        Dictionary of ion concentrations.
    """
    if template not in DEFAULT_WATER_TEMPLATES:
        raise ValueError(
            f"Unknown water chemistry template '{template}'. "
            f"Valid options: {', '.join(DEFAULT_WATER_TEMPLATES)}"
        )
    return dict(DEFAULT_WATER_TEMPLATES[template])


def prepare_water_chemistry(
    water_chemistry_json: Optional[str],
    *,
    default_template: str = "municipal",
) -> WaterChemistryData:
    """
    Parse (or synthesize) water chemistry and build a PHREEQC-ready solution.

    Args:
        water_chemistry_json: JSON string from caller (RO MCP compatible).
        default_template: Template to use when no JSON is provided.

    Returns:
        WaterChemistryData with validated inputs and derived properties.
    """
    if water_chemistry_json:
        ion_dict = parse_water_chemistry_json(water_chemistry_json)
        source = "user"
    else:
        ion_dict = get_default_water_chemistry(default_template)
        source = f"default:{default_template}"
        logger.info(
            "No water chemistry provided; using %s template for background ions.",
            default_template,
        )

    charge_balance = calculate_charge_balance(ion_dict)
    if abs(charge_balance) > 5.0:
        logger.warning("Significant charge imbalance detected: %.1f%%", charge_balance)

    phreeqc_solution = build_phreeqc_solution(ion_dict)

    return WaterChemistryData(
        ion_composition_mg_l=ion_dict,
        phreeqc_solution_mg_l=phreeqc_solution,
        charge_balance_percent=charge_balance,
        source=source,
    )
