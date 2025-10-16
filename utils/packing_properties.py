"""
Packing Properties Module - Load packing catalog from pack.json

Provides functions to:
1. Load packing properties from databases/pack.json
2. Look up packing by name, size, or material
3. Get packing factor (Fp), surface area, void fraction

Reference:
- Perry's Handbook 8th Ed, Table 14-13
- pack.json database with 9 standard packings
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Database path
DB_DIR = Path(__file__).parent.parent / "databases"
PACK_JSON = DB_DIR / "pack.json"


def load_packing_catalog() -> Dict[str, Dict[str, Any]]:
    """
    Load packing catalog from pack.json.

    Returns:
        Dict mapping packing_id to packing properties:
        {
            "Metal_Pall_Rings_25mm": {
                "name": "Metal Pall Rings",
                "nominal_size_mm": 25,
                "packing_factor_m_inv": 220,
                "surface_area_m2_m3": 220,
                "void_fraction": 0.75,
                ...
            },
            ...
        }
    """
    if not PACK_JSON.exists():
        logger.error(f"Packing catalog not found: {PACK_JSON}")
        return {}

    with open(PACK_JSON, 'r') as f:
        catalog = json.load(f)

    logger.info(f"Loaded {len(catalog)} packings from pack.json")
    return catalog


def get_packing_by_id(packing_id: str) -> Optional[Dict[str, Any]]:
    """
    Get packing properties by packing ID.

    Args:
        packing_id: Packing identifier (e.g., "Metal_Pall_Rings_25mm")

    Returns:
        Dict with packing properties, or None if not found
    """
    catalog = load_packing_catalog()

    if packing_id not in catalog:
        logger.warning(f"Packing ID '{packing_id}' not found in catalog")
        return None

    return catalog[packing_id]


def find_packings(
    name: Optional[str] = None,
    material: Optional[str] = None,
    size_mm: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Find packings matching criteria.

    Args:
        name: Packing name (partial match, case-insensitive)
        material: Material type (e.g., "Metal", "Plastic", "Ceramic")
        size_mm: Nominal size in mm

    Returns:
        List of matching packings with properties
    """
    catalog = load_packing_catalog()
    matches = []

    for packing_id, props in catalog.items():
        # Check name match
        if name and name.lower() not in props.get('name', '').lower():
            continue

        # Check material match
        if material and material.lower() != props.get('material', '').lower():
            continue

        # Check size match
        if size_mm is not None:
            packing_size = props.get('nominal_size_mm')
            if packing_size is None or abs(packing_size - size_mm) > 0.1:
                continue

        # All criteria matched
        matches.append({
            'packing_id': packing_id,
            **props
        })

    logger.info(f"Found {len(matches)} packings matching criteria")
    return matches


def get_default_packing(application: str = "general") -> Dict[str, Any]:
    """
    Get default packing for an application.

    Args:
        application: Application type:
            - "CO2": CO2 stripping (alkalinity removal)
            - "H2S": H2S stripping (sulfide removal)
            - "VOC": VOC stripping (volatile organic removal)
            - "general": General purpose

    Returns:
        Dict with packing properties

    Recommendation:
        - Metal Pall Rings 50mm: General purpose, good capacity
        - Plastic Pall Rings 50mm: Corrosive systems (H2S, CO2)
        - Ceramic Intalox Saddles 25mm: High efficiency for VOCs
    """
    if application.upper() in ["H2S", "CO2"]:
        # Plastic for corrosive gases
        packing_id = "Plastic_Pall_Rings_50mm"
    elif application.upper() == "VOC":
        # Ceramic Intalox for VOC - higher surface area
        packing_id = "Ceramic_Intalox_Saddles_25mm"
    else:
        # Metal Pall rings for general purpose
        packing_id = "Metal_Pall_Rings_50mm"

    packing = get_packing_by_id(packing_id)

    if not packing:
        logger.warning(f"Default packing '{packing_id}' not found, using fallback")
        # Fallback: return first available packing
        catalog = load_packing_catalog()
        if catalog:
            first_id = list(catalog.keys())[0]
            packing = catalog[first_id].copy()
            packing['packing_id'] = first_id
    else:
        # Add packing_id to the returned dict
        packing = packing.copy()
        packing['packing_id'] = packing_id

    return packing


def list_available_packings() -> List[str]:
    """
    List all available packing IDs in catalog.

    Returns:
        List of packing IDs
    """
    catalog = load_packing_catalog()
    return list(catalog.keys())


if __name__ == "__main__":
    # Test the module
    logging.basicConfig(level=logging.INFO)

    print("=== Packing Properties Module Test ===\n")

    # 1. Load catalog
    print("1. Available packings:")
    packings = list_available_packings()
    for p in packings:
        print(f"   - {p}")
    print()

    # 2. Get specific packing
    print("2. Metal Pall Rings 50mm properties:")
    packing = get_packing_by_id("Metal_Pall_Rings_50mm")
    if packing:
        print(f"   Name: {packing['name']}")
        print(f"   Size: {packing['nominal_size_mm']} mm ({packing['nominal_size_in']} in)")
        print(f"   Fp: {packing['packing_factor_m_inv']} m^-1")
        print(f"   Surface area: {packing['surface_area_m2_m3']} m^2/m^3")
        print(f"   Void fraction: {packing['void_fraction']:.2f}")
    print()

    # 3. Find packings by criteria
    print("3. Find all 50mm packings:")
    matches = find_packings(size_mm=50)
    for m in matches:
        print(f"   - {m['name']} ({m['material']}): Fp={m['packing_factor_m_inv']} m^-1")
    print()

    # 4. Get default packings for applications
    print("4. Default packings by application:")
    for app in ["CO2", "H2S", "VOC", "general"]:
        default = get_default_packing(app)
        print(f"   {app}: {default['name']} {default['nominal_size_mm']}mm")
