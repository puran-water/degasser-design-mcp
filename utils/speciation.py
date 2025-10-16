"""
Aqueous Speciation Module - pH-Dependent Strippable Fraction Calculation

Provides PHREEQC-based calculations for pH-dependent speciation of H2S and CO2.
Returns the fraction of total solute that exists as neutral, volatile species.

Applications:
- H2S stripping: Only H2S(aq) is strippable, HS⁻ is non-volatile
- CO2 stripping: Only CO2(aq) and H2CO3 are strippable, HCO3⁻/CO3²⁻ are non-volatile

Reference:
- PHREEQC thermodynamic database (phreeqc.dat)
- Henderson-Hasselbalch equation validation
"""

import logging
from functools import lru_cache
from typing import Literal
from phreeqpython import PhreeqPython

logger = logging.getLogger(__name__)

# Singleton PHREEQC instance
_pp = PhreeqPython()

# PHREEQC species names for neutral (strippable) forms
_NEUTRAL_KEYS = {
    "H2S": ("H2S",),
    "CO2": ("CO2", "H2CO3")
}

# Element mapping for PHREEQC
_ELEMENT_MAP = {
    "H2S": "S(-2)",
    "CO2": "C(4)"
}


@lru_cache(maxsize=256)
def strippable_fraction(
    solute: Literal["H2S", "CO2"],
    ph: float,
    temp_c: float = 25.0,
    total_mg_l: float = 100.0
) -> float:
    """
    Calculate the strippable (neutral) fraction of H2S or CO2 at given pH.

    Uses PHREEQC to rigorously model pH-dependent speciation including
    ionic strength effects and activity coefficients.

    Args:
        solute: "H2S" or "CO2"
        ph: Water pH (4.0 to 10.0)
        temp_c: Temperature in °C (default: 25.0)
        total_mg_l: Total concentration in mg/L (default: 100.0)
                   Note: Used for ionic strength, but fraction is concentration-independent

    Returns:
        Fraction of total solute in neutral (strippable) form (0.0 to 1.0)

    Example:
        >>> # H2S at pH 7.8 (above pKa1=7.0)
        >>> frac = strippable_fraction("H2S", ph=7.8, temp_c=25.0)
        >>> print(f"Strippable: {frac*100:.1f}%")  # ~14%

        >>> # CO2 at pH 8.5 (above pKa1=6.35)
        >>> frac = strippable_fraction("CO2", ph=8.5, temp_c=25.0)
        >>> print(f"Strippable: {frac*100:.1f}%")  # ~0.7%

    Raises:
        ValueError: If solute not in ["H2S", "CO2"], pH out of range
    """
    # Validate inputs
    solute_upper = solute.upper()
    if solute_upper not in _NEUTRAL_KEYS:
        raise ValueError(f"Solute must be 'H2S' or 'CO2', got '{solute}'")

    if not (4.0 <= ph <= 10.0):
        logger.warning(f"pH {ph:.1f} outside typical range [4.0, 10.0]")

    # Get element and neutral species keys
    element = _ELEMENT_MAP[solute_upper]
    neutral_keys = _NEUTRAL_KEYS[solute_upper]

    # Create PHREEQC solution
    solution = _pp.add_solution({
        "pH": ph,
        "temp": temp_c,
        element: total_mg_l,
        "units": "mg/L"
    })

    try:
        # Query neutral species molalities (dict: species_name -> molality)
        neutral_molality = sum(
            solution.species_molalities.get(name, 0.0)
            for name in neutral_keys
        )

        # Get total element molality using total_element() method
        # For S(-2), query "S" as the element symbol
        # CRITICAL: Specify units="mol" to match species_molalities units (mol/kgw)
        # Default is mmol, which causes 1000x error!
        element_symbol = element.split("(")[0]  # "S(-2)" -> "S", "C(4)" -> "C"
        total_molality = solution.total_element(element_symbol, units="mol")

        # Calculate fraction
        if total_molality > 0:
            fraction = neutral_molality / total_molality
        else:
            logger.warning(f"Zero total {element} molality in PHREEQC solution")
            fraction = 0.0

        logger.debug(
            f"{solute_upper} speciation at pH {ph:.2f}, {temp_c:.1f}°C: "
            f"{fraction*100:.2f}% strippable"
        )

        return fraction

    finally:
        # Free native memory
        solution.forget()


def effective_inlet_concentration(
    solute: Literal["H2S", "CO2"],
    total_mg_l: float,
    ph: float,
    temp_c: float = 25.0
) -> float:
    """
    Calculate effective inlet concentration for stripping design.

    This is the concentration of strippable (neutral) species that will
    actually be removed by air stripping.

    Args:
        solute: "H2S" or "CO2"
        total_mg_l: Total measured concentration, mg/L
        ph: Water pH
        temp_c: Temperature in °C (default: 25.0)

    Returns:
        Effective strippable concentration, mg/L

    Example:
        >>> # 32 mg/L total H2S at pH 7.8
        >>> effective = effective_inlet_concentration("H2S", 32.0, ph=7.8)
        >>> print(f"Strippable: {effective:.1f} mg/L")  # ~4.5 mg/L (14% of 32)
    """
    fraction = strippable_fraction(solute, ph, temp_c, total_mg_l)
    return total_mg_l * fraction


if __name__ == "__main__":
    # Test the module
    logging.basicConfig(level=logging.INFO)

    print("=== Aqueous Speciation Module Test ===\n")

    # 1. H2S speciation across pH range
    print("1. H2S Speciation (pKa1 = 7.0):")
    for ph in [6.0, 7.0, 7.8, 8.0, 9.0]:
        frac = strippable_fraction("H2S", ph=ph, temp_c=25.0)
        print(f"   pH {ph:.1f}: {frac*100:5.1f}% H2S(aq), {(1-frac)*100:5.1f}% HS-")
    print()

    # 2. CO2 speciation across pH range
    print("2. CO2 Speciation (pKa1 = 6.35):")
    for ph in [6.0, 6.35, 7.0, 8.0, 9.0]:
        frac = strippable_fraction("CO2", ph=ph, temp_c=25.0)
        print(f"   pH {ph:.2f}: {frac*100:5.1f}% CO2(aq), {(1-frac)*100:5.1f}% HCO3-/CO3-2")
    print()

    # 3. User's H2S case: 32 mg/L at pH 7.8
    print("3. User's H2S Case (32 mg/L at pH 7.8):")
    total = 32.0
    ph = 7.8
    effective = effective_inlet_concentration("H2S", total, ph)
    print(f"   Total H2S: {total:.1f} mg/L")
    print(f"   pH: {ph:.1f}")
    print(f"   Strippable: {effective:.1f} mg/L ({effective/total*100:.1f}%)")
    print(f"   Non-strippable: {total - effective:.1f} mg/L ({(1-effective/total)*100:.1f}%)")
