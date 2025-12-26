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

import json
import logging
import os
import sys
import uuid
import warnings
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Import job management utilities
from utils.job_manager import JobManager
from utils.path_utils import get_python_executable

# Configure logging - CRITICAL: Use INFO level and stderr-only to prevent stdout pollution
# Pyomo/IDAES DEBUG spam breaks MCP's JSON-RPC transport over stdio
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler(sys.stderr)  # Explicit stderr to avoid stdout pollution
    ]
)
logger = logging.getLogger("degasser-design-mcp")

# Suppress noisy library DEBUG/INFO logs that leak to stderr and corrupt MCP transport
noisy_libraries = ["pyomo", "pyomo.core", "pyomo.common", "pyomo.environ",
                   "idaes", "idaes.core", "watertap", "qsdsan", "qsd"]
for lib_name in noisy_libraries:
    lib_logger = logging.getLogger(lib_name)
    lib_logger.setLevel(logging.WARNING)
    lib_logger.propagate = False

# CRITICAL: Suppress pint.util deprecation warnings that bypass redirect_stderr()
# These warnings come from Pyomo's use of pint and break MCP's JSON-RPC transport
for pint_logger_name in ("pint", "pint.util", "pint.registry"):
    pint_logger = logging.getLogger(pint_logger_name)
    pint_logger.setLevel(logging.ERROR)  # Only errors, no warnings
    pint_logger.propagate = False
    if not pint_logger.handlers:
        pint_logger.addHandler(logging.NullHandler())

# Also suppress pint warnings at the warnings module level (belt-and-suspenders)
warnings.filterwarnings(
    "ignore",
    message="Calling the getitem method from a UnitRegistry is deprecated",
    module=r"pint\.util"
)

# Initialize the MCP server
mcp = FastMCP("degasser-design-calculator")

# Import core tools
# Phase 1: Tier 1 Heuristic Sizing (COMPLETE)
from tools.heuristic_sizing import heuristic_sizing, list_available_packings

# Phase 2: Tier 2 PHREEQC Gas-Liquid Equilibrium (COMPLETE)
from tools.simulation_sizing import staged_column_simulation

# Phase 3: Tier 3 WaterTAP Economic Costing (COMPLETE)
from tools.watertap_costing import cost_degasser_system_async

# Phase 4: Report Generation & Batch Optimization (TO BE IMPLEMENTED)
# from tools.report_generator import generate_degasser_report
# from tools.batch_optimization import batch_optimize_degasser

# Create wrapper for heuristic_sizing that returns dict for MCP
from dataclasses import asdict, fields
from pydantic import BaseModel


def convert_to_dict(obj):
    """Recursively convert dataclasses and Pydantic models to dicts."""
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    elif hasattr(obj, '__dataclass_fields__'):
        result = {}
        for field in fields(obj):
            value = getattr(obj, field.name)
            result[field.name] = convert_to_dict(value)
        return result
    elif isinstance(obj, list):
        return [convert_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convert_to_dict(v) for k, v in obj.items()}
    else:
        return obj


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
    # Note: asdict() doesn't handle nested Pydantic models, so use convert_to_dict
    return convert_to_dict(result)

# Create combined tool for Tier 1 + optional Tier 2 + optional Tier 3
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
    find_optimal_stages: bool = True,
    run_tier3: bool = False,
    packing_type: str = "plastic_pall"
):
    """
    Combined Tier 1 + optional Tier 2 + optional Tier 3.

    Run Tier 1 heuristic sizing, optionally continue with Tier 2 staged
    column simulation, and optionally run Tier 3 economic costing.

    For Tier 2 and Tier 3, this uses the background job pattern to avoid
    MCP STDIO transport timeout issues. Returns a job_id immediately;
    use get_job_status() and get_job_results() to monitor and retrieve results.

    Args:
        (same as heuristic_sizing plus:)
        run_tier2: Whether to run Tier 2 simulation (default: False)
        num_stages_initial: Initial/fixed stage count for Tier 2 (default: None, auto-find)
        find_optimal_stages: If True, use bisection to find optimal N (default: True)
        run_tier3: Whether to run Tier 3 economic costing (default: False)
        packing_type: Packing material for costing (plastic_pall, ceramic_raschig, etc.)

    Returns:
        If run_tier2=True or run_tier3=True: Job status dict with job_id for polling
        Otherwise: Dict with Tier 1 results only
    """
    # Build params dict for background jobs
    params = {
        "application": application,
        "water_flow_rate_m3_h": water_flow_rate_m3_h,
        "inlet_concentration_mg_L": inlet_concentration_mg_L,
        "outlet_concentration_mg_L": outlet_concentration_mg_L,
        "air_water_ratio": air_water_ratio,
        "temperature_c": temperature_c,
        "packing_id": packing_id,
        "henry_constant_25C": henry_constant_25C,
        "water_ph": water_ph,
        "water_chemistry_json": water_chemistry_json,
        "include_blower_sizing": include_blower_sizing,
        "blower_efficiency_override": blower_efficiency_override,
        "motor_efficiency": motor_efficiency,
        "num_stages_initial": num_stages_initial,
        "find_optimal_stages": find_optimal_stages,
        "packing_type": packing_type
    }
    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    # If Tier 3 requested, spawn background job (highest tier takes precedence)
    if run_tier3:
        manager = JobManager()
        job_id = str(uuid.uuid4())[:8]
        job_dir = Path("jobs") / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Write params to job directory
        with open(job_dir / "params.json", "w") as f:
            json.dump(params, f, indent=2)

        # Build command for tier3_cli.py
        python_exe = get_python_executable()
        cmd = [python_exe, "utils/tier3_cli.py", "--job-dir", str(job_dir)]

        # Start background job
        job = await manager.execute(cmd=cmd, cwd=".", job_id=job_id)

        # Register state patch for auto-hydration
        job["state_patch"] = {
            "field": "tier3_results",
            "result_file": "tier3_results.json"
        }
        manager._save_job_metadata(job)

        logger.info(f"Started Tier 3 background job: {job_id}")

        return {
            "status": "job_started",
            "job_id": job_id,
            "tier": "tier3",
            "message": "Tier 3 economic costing job started. Use get_job_status(job_id) to check progress.",
            "estimated_time_seconds": 30
        }

    # If Tier 2 requested, spawn background job
    if run_tier2:
        manager = JobManager()
        job_id = str(uuid.uuid4())[:8]
        job_dir = Path("jobs") / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Write params to job directory
        with open(job_dir / "params.json", "w") as f:
            json.dump(params, f, indent=2)

        # Build command for tier2_cli.py
        python_exe = get_python_executable()
        cmd = [python_exe, "utils/tier2_cli.py", "--job-dir", str(job_dir)]

        # Start background job
        job = await manager.execute(cmd=cmd, cwd=".", job_id=job_id)

        # Register state patch for auto-hydration
        job["state_patch"] = {
            "field": "tier2_results",
            "result_file": "tier2_results.json"
        }
        manager._save_job_metadata(job)

        logger.info(f"Started Tier 2 background job: {job_id}")

        return {
            "status": "job_started",
            "job_id": job_id,
            "tier": "tier2",
            "message": "Tier 2 PHREEQC simulation job started. Use get_job_status(job_id) to check progress.",
            "estimated_time_seconds": 20
        }

    # Tier 1 only - run synchronously (fast, <1 sec)
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

    # Convert to dictionary (handle Pydantic BaseModel objects)
    def convert_to_dict(obj):
        """Recursively convert dataclasses and Pydantic models to dicts."""
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        elif hasattr(obj, '__dataclass_fields__'):
            from dataclasses import fields
            result = {}
            for field in fields(obj):
                value = getattr(obj, field.name)
                result[field.name] = convert_to_dict(value)
            return result
        elif isinstance(obj, list):
            return [convert_to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: convert_to_dict(v) for k, v in obj.items()}
        else:
            return obj

    return convert_to_dict(tier1_outcome)

# Register tools
# Tool 1: Fast Perry's-based heuristic sizing
mcp.tool()(heuristic_sizing_mcp)

# Tool 2: List available packing catalog
mcp.tool()(list_available_packings)

# Tool 3: Combined Tier 1 + optional Tier 2 + optional Tier 3
mcp.tool()(combined_simulation_mcp)

# Note: cost_degasser_system_async is NOT registered as MCP tool because it
# requires Tier1Outcome dataclass parameter which cannot be serialized via MCP.
# It remains available for Python API use. For MCP access to Tier 3 costing,
# use combined_simulation_mcp with run_tier3=True parameter.


# =============================================================================
# Job Management Tools (for background Tier 2 & Tier 3 operations)
# =============================================================================

async def get_job_status(job_id: str) -> dict:
    """
    Get the current status of a background job.

    Use this to poll for job completion after calling combined_simulation_mcp
    with run_tier2=True or run_tier3=True.

    Args:
        job_id: Job identifier returned from combined_simulation_mcp

    Returns:
        Dict with job_id, status (starting/running/completed/failed),
        elapsed_time_seconds, and progress hints if available.
    """
    manager = JobManager()
    return await manager.get_status(job_id)


async def get_job_results(job_id: str) -> dict:
    """
    Get results from a completed background job.

    Call this after get_job_status indicates the job has completed.

    Args:
        job_id: Job identifier returned from combined_simulation_mcp

    Returns:
        Dict with job_id, status, total_time_seconds, and results
        (full Tier 1 + Tier 2/3 output).
    """
    manager = JobManager()
    return await manager.get_results(job_id)


async def list_jobs(status_filter: str = None, limit: int = 20) -> dict:
    """
    List all background jobs with optional status filter.

    Args:
        status_filter: Filter by status ("running", "completed", "failed", or None for all)
        limit: Maximum number of jobs to return (default: 20)

    Returns:
        Dict with jobs list, total count, and concurrency info.
    """
    manager = JobManager()
    return await manager.list_jobs(status_filter, limit)


async def terminate_job(job_id: str) -> dict:
    """
    Terminate a running background job.

    Args:
        job_id: Job identifier to terminate

    Returns:
        Dict with termination status.
    """
    manager = JobManager()
    return await manager.terminate_job(job_id)


async def wait_for_job(
    job_id: str,
    timeout_seconds: int = 300,
    poll_interval_seconds: float = 2.0
) -> dict:
    """
    Wait for a background job to complete.

    This is a blocking convenience tool that polls get_job_status until
    the job completes, fails, or times out. Use this instead of manually
    calling get_job_status in a loop.

    Args:
        job_id: Job identifier from combined_simulation_mcp
        timeout_seconds: Maximum time to wait (default 5 minutes)
        poll_interval_seconds: How often to check status (default 2 seconds)

    Returns:
        Dict with job results if completed, or error status if failed/timeout.
    """
    import time as time_module
    import asyncio

    manager = JobManager()
    start = time_module.time()

    while time_module.time() - start < timeout_seconds:
        status = await manager.get_status(job_id)

        if status.get("status") == "completed":
            # Job completed - return full results
            return await manager.get_results(job_id)

        if status.get("status") == "failed":
            # Job failed - return error info
            return {
                "job_id": job_id,
                "status": "failed",
                "error": status.get("error", "Unknown error"),
                "exit_code": status.get("exit_code")
            }

        if status.get("status") == "terminated":
            return {
                "job_id": job_id,
                "status": "terminated",
                "error": "Job was terminated before completion"
            }

        # Still running - wait and try again
        await asyncio.sleep(poll_interval_seconds)

    # Timeout reached
    return {
        "job_id": job_id,
        "status": "timeout",
        "error": f"Job did not complete within {timeout_seconds} seconds",
        "last_progress": (await manager.get_status(job_id)).get("progress")
    }


# Register job management tools
mcp.tool()(get_job_status)
mcp.tool()(get_job_results)
mcp.tool()(list_jobs)
mcp.tool()(terminate_job)
mcp.tool()(wait_for_job)


# Tool 4: Professional HTML reports (Phase 4)
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
            logger.info(f"  OK {db_name}: {db_path.name} ({size_mb:.2f} MB)")
        else:
            logger.warning(f"  [X] {db_name}: {db_path.name} NOT FOUND")

    # Log server status
    logger.info("\n=== DEGASSER DESIGN MCP SERVER ===")
    logger.info("\n[*] THREE-TIER ARCHITECTURE:")
    logger.info("  Tier 1: Fast Heuristic Sizing (<1 sec)")
    logger.info("    - Perry's Handbook correlations")
    logger.info("    - Eckert flooding, HTU/NTU methods")
    logger.info("  Tier 2: PHREEQC Gas-Liquid Equilibrium (10-30 sec)")
    logger.info("    - GAS_PHASE blocks for CO2, H2S, VOC")
    logger.info("    - Multi-stage tower simulation")
    logger.info("  Tier 3: WaterTAP Economic Costing (5-10 sec)")
    logger.info("    - CAPEX, OPEX, LCOW calculations")
    logger.info("    - EPA-WBS correlations")

    logger.info("\n[*] APPLICATIONS:")
    logger.info("  1. CO2 Stripping (Alkalinity Removal)")
    logger.info("     - RO pretreatment, boiler feedwater")
    logger.info("     - Air/water: 20:1-50:1, pH: 4.5-5.5")
    logger.info("  2. H2S Stripping (Sulfide Removal)")
    logger.info("     - Groundwater, industrial wastewater")
    logger.info("     - Air/water: 30:1-100:1, pH: 4.0-5.0")
    logger.info("  3. VOC Stripping (Volatile Organic Removal)")
    logger.info("     - Contaminated groundwater remediation")
    logger.info("     - Henry's law governed mass transfer")

    logger.info("\n[*] DATA SOURCES:")
    logger.info("  • Perry's Chemical Engineers' Handbook (semantic search)")
    logger.info("  • henrys-law.org SQLite database (2 MB, 4632 compounds)")
    logger.info("  • VOC properties from Air-stripping-column repo")
    logger.info("  • Packing catalog with Eckert correlation data")

    logger.info("\n[OK] IMPLEMENTATION STATUS: PHASES 1-3 COMPLETE")
    logger.info("  [OK] Phase 0: Data Acquisition")
    logger.info("     - Downloaded databases from GitHub")
    logger.info("     - Generated unified VOC properties")
    logger.info("     - Created PHREEQC phases definitions")
    logger.info("  [OK] Phase 1: Tier 1 Heuristic Sizing (COMPLETE)")
    logger.info("     - Perry's Eckert GPDC flooding correlation")
    logger.info("     - HTU/NTU method with Eq 14-158")
    logger.info("     - 9 packings in catalog with actual properties")
    logger.info("  [OK] Phase 2: Tier 2 PHREEQC Simulation (COMPLETE)")
    logger.info("     - Multi-stage tower with pH-coupled equilibrium")
    logger.info("     - Bisection for optimal stage count")
    logger.info("  [OK] Phase 3: Tier 3 WaterTAP Costing (COMPLETE)")
    logger.info("     - Shoener 2016 blower costing (QSDsan)")
    logger.info("     - Tang 1984 vessel costing (WaterTAP)")
    logger.info("     - EPA WBS packing & internals costs")
    logger.info("     - Economic metrics: NPV, LCOW, payback")
    logger.info("     - MCP tools: cost_degasser_system_async, combined_simulation_mcp")
    logger.info("  [PENDING] Phase 4: Reports & Optimization (PENDING)")

    logger.info("\n=== SERVER READY FOR DEVELOPMENT ===")

    # Start the server
    mcp.run()
