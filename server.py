"""
Degasser/Stripping Tower Design MCP Server.

This server provides packed tower degasser and stripping column design tools including:
- Tier 1: Fast heuristic sizing using Perry's Handbook correlations
- Tier 2: PHREEQC gas-liquid equilibrium modeling
- Tier 3: WaterTAP economic costing and lifecycle analysis

Applications:
- CO2 stripping (alkalinity removal for RO pretreatment)
- H2S stripping (sulfide removal from groundwater)
- VOC stripping (volatile organic compound removal)

Author: Claude AI
"""

import logging
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Configure logging with debug support
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("degasser-design-mcp")

# Initialize the MCP server
mcp = FastMCP("degasser-design-calculator")

# Import core tools
# Phase 1: Tier 1 Heuristic Sizing (COMPLETE)
from tools.heuristic_sizing import heuristic_sizing, list_available_packings

# Phase 2: Tier 2 PHREEQC Gas-Liquid Equilibrium (85% COMPLETE)
from tools.simulation_sizing import staged_column_simulation

# Phase 3: Tier 3 WaterTAP Economic Costing (TO BE IMPLEMENTED)
# from tools.watertap_costing import cost_degasser_system

# Phase 4: Report Generation & Batch Optimization (TO BE IMPLEMENTED)
# from tools.report_generator import generate_degasser_report
# from tools.batch_optimization import batch_optimize_degasser

# Create wrapper for heuristic_sizing that returns dict for MCP
from dataclasses import asdict

async def heuristic_sizing_mcp(
    application: str,
    water_flow_rate_m3_h: float,
    inlet_concentration_mg_L: float,
    outlet_concentration_mg_L: float,
    air_water_ratio: float = 30.0,
    temperature_c: float = 25.0,
    packing_id: str = None,
    henry_constant_25C: float = None,
    water_ph: float = None,
    water_chemistry_json: str = None,
    include_blower_sizing: bool = True,
    blower_efficiency_override: float = None,
    motor_efficiency: float = 0.92
):
    """MCP wrapper for heuristic_sizing that returns dictionary."""
    result = await heuristic_sizing(
        application=application,
        water_flow_rate_m3_h=water_flow_rate_m3_h,
        inlet_concentration_mg_L=inlet_concentration_mg_L,
        outlet_concentration_mg_L=outlet_concentration_mg_L,
        air_water_ratio=air_water_ratio,
        temperature_c=temperature_c,
        packing_id=packing_id,
        henry_constant_25C=henry_constant_25C,
        water_ph=water_ph,
        water_chemistry_json=water_chemistry_json,
        include_blower_sizing=include_blower_sizing,
        blower_efficiency_override=blower_efficiency_override,
        motor_efficiency=motor_efficiency
    )
    # Convert Tier1Outcome dataclass to dictionary for MCP serialization
    return asdict(result)

# Create combined tool for Tier 1 + optional Tier 2
async def combined_simulation_mcp(
    application: str,
    water_flow_rate_m3_h: float,
    inlet_concentration_mg_L: float,
    outlet_concentration_mg_L: float,
    air_water_ratio: float = 30.0,
    temperature_c: float = 25.0,
    packing_id: str = None,
    henry_constant_25C: float = None,
    water_ph: float = None,
    water_chemistry_json: str = None,
    include_blower_sizing: bool = True,
    blower_efficiency_override: float = None,
    motor_efficiency: float = 0.92,
    run_tier2: bool = False,
    num_stages_initial: int = None,
    find_optimal_stages: bool = True
):
    """
    Combined Tier 1 + optional Tier 2 simulation.

    Run Tier 1 heuristic sizing, and optionally continue with
    Tier 2 staged column simulation for pH-coupled rigorous design.

    Args:
        (same as heuristic_sizing plus:)
        run_tier2: Whether to run Tier 2 simulation (default: False)
        num_stages_initial: Initial/fixed stage count for Tier 2 (default: None, auto-find)
        find_optimal_stages: If True, use bisection to find optimal N (default: True)

    Returns:
        Dict with Tier 1 results, and 'tier2' key if run_tier2=True
    """
    # Run Tier 1
    tier1_outcome = await heuristic_sizing(
        application=application,
        water_flow_rate_m3_h=water_flow_rate_m3_h,
        inlet_concentration_mg_L=inlet_concentration_mg_L,
        outlet_concentration_mg_L=outlet_concentration_mg_L,
        air_water_ratio=air_water_ratio,
        temperature_c=temperature_c,
        packing_id=packing_id,
        henry_constant_25C=henry_constant_25C,
        water_ph=water_ph,
        water_chemistry_json=water_chemistry_json,
        include_blower_sizing=include_blower_sizing,
        blower_efficiency_override=blower_efficiency_override,
        motor_efficiency=motor_efficiency
    )

    # Convert to dictionary
    result = asdict(tier1_outcome)

    # Optionally run Tier 2
    if run_tier2:
        try:
            logger.info("Running Tier 2 staged column simulation...")
            tier2_result = staged_column_simulation(
                tier1_outcome,
                num_stages_initial=num_stages_initial,
                find_optimal_stages=find_optimal_stages,
                convergence_tolerance=0.01,
                max_inner_iterations=200,  # FIX 5: Increased to 200 for improved convergence
                validate_mass_balance_flag=True
            )
            result['tier2'] = tier2_result
            logger.info(f"Tier 2 complete: {tier2_result['theoretical_stages']} stages, "
                       f"{tier2_result['tower_height_m']:.1f}m height")
        except Exception as e:
            logger.error(f"Tier 2 simulation failed: {e}")
            result['tier2_error'] = str(e)

    return result

# Register tools
# Tool 1: Fast Perry's-based heuristic sizing
mcp.tool()(heuristic_sizing_mcp)

# Tool 2: List available packing catalog
mcp.tool()(list_available_packings)

# Tool 3: Combined Tier 1 + optional Tier 2 simulation
mcp.tool()(combined_simulation_mcp)

# Tool 3: PHREEQC gas-liquid equilibrium (Phase 2)
# mcp.tool()(simulate_gas_stripping)

# Tool 4: WaterTAP economic analysis (Phase 3)
# mcp.tool()(cost_degasser_system)

# Tool 5: Professional HTML reports (Phase 4)
# mcp.tool()(generate_degasser_report)

# Tool 6: Parameter sweeps & optimization (Phase 4)
# mcp.tool()(batch_optimize_degasser)

# Check for required dependencies
try:
    from phreeqpython import PhreeqPython
    PHREEQPYTHON_AVAILABLE = True
    logger.info("PhreeqPython is available")
except ImportError:
    PHREEQPYTHON_AVAILABLE = False
    logger.warning("PhreeqPython not available - PHREEQC tools will not work")

# Check for database files
DB_DIR = Path(__file__).parent / "databases"
DATABASES = {
    "voc_properties": DB_DIR / "voc_properties.json",
    "packing_catalog": DB_DIR / "pack.json",
    "water_properties": DB_DIR / "ppow.json",
    "henrys_law": DB_DIR / "henrys_law.db",
    "phreeqc_voc_phases": DB_DIR / "voc_phases.dat"
}

if __name__ == "__main__":
    logger.info("Starting Degasser Design MCP server...")
    logger.info(f"PhreeqPython available: {PHREEQPYTHON_AVAILABLE}")

    # Check database files
    logger.info("\n=== CHECKING DATABASE FILES ===")
    for db_name, db_path in DATABASES.items():
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            logger.info(f"  ✓ {db_name}: {db_path.name} ({size_mb:.2f} MB)")
        else:
            logger.warning(f"  ✗ {db_name}: {db_path.name} NOT FOUND")

    # Log server status
    logger.info("\n=== DEGASSER DESIGN MCP SERVER ===")
    logger.info("\n📋 THREE-TIER ARCHITECTURE:")
    logger.info("  Tier 1: Fast Heuristic Sizing (<1 sec)")
    logger.info("    - Perry's Handbook correlations")
    logger.info("    - Eckert flooding, HTU/NTU methods")
    logger.info("  Tier 2: PHREEQC Gas-Liquid Equilibrium (10-30 sec)")
    logger.info("    - GAS_PHASE blocks for CO2, H2S, VOC")
    logger.info("    - Multi-stage tower simulation")
    logger.info("  Tier 3: WaterTAP Economic Costing (5-10 sec)")
    logger.info("    - CAPEX, OPEX, LCOW calculations")
    logger.info("    - EPA-WBS correlations")

    logger.info("\n🎯 APPLICATIONS:")
    logger.info("  1. CO2 Stripping (Alkalinity Removal)")
    logger.info("     - RO pretreatment, boiler feedwater")
    logger.info("     - Air/water: 20:1-50:1, pH: 4.5-5.5")
    logger.info("  2. H2S Stripping (Sulfide Removal)")
    logger.info("     - Groundwater, industrial wastewater")
    logger.info("     - Air/water: 30:1-100:1, pH: 4.0-5.0")
    logger.info("  3. VOC Stripping (Volatile Organic Removal)")
    logger.info("     - Contaminated groundwater remediation")
    logger.info("     - Henry's law governed mass transfer")

    logger.info("\n📊 DATA SOURCES:")
    logger.info("  • Perry's Chemical Engineers' Handbook (semantic search)")
    logger.info("  • henrys-law.org SQLite database (2 MB, 4632 compounds)")
    logger.info("  • VOC properties from Air-stripping-column repo")
    logger.info("  • Packing catalog with Eckert correlation data")

    logger.info("\n✅ IMPLEMENTATION STATUS: PHASE 1 COMPLETE")
    logger.info("  ✅ Phase 0: Data Acquisition")
    logger.info("     - Downloaded databases from GitHub")
    logger.info("     - Generated unified VOC properties")
    logger.info("     - Created PHREEQC phases definitions")
    logger.info("  ✅ Phase 1: Tier 1 Heuristic Sizing (COMPLETE)")
    logger.info("     - Perry's Eckert GPDC flooding correlation")
    logger.info("     - HTU/NTU method with Eq 14-158")
    logger.info("     - 9 packings in catalog with actual properties")
    logger.info("     - MCP tools: heuristic_sizing, list_available_packings, combined_simulation")
    logger.info("  🔧 Phase 2: Tier 2 PHREEQC Simulation (85% COMPLETE)")
    logger.info("  ⏳ Phase 3: Tier 3 WaterTAP Costing (PENDING)")
    logger.info("  ⏳ Phase 4: Reports & Optimization (PENDING)")

    logger.info("\n=== SERVER READY FOR DEVELOPMENT ===")

    # Start the server
    mcp.run()
