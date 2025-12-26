#!/usr/bin/env python
"""
CLI runner for Tier 3 WaterTAP economic costing.

This provides a subprocess entry point for the JobManager pattern.
Heavy imports (Pyomo, IDAES) happen here, not in the MCP server.

Usage:
    python utils/tier3_cli.py --job-dir jobs/abc123

The job directory should contain:
    - params.json: Input parameters for heuristic_sizing + costing options

Outputs:
    - tier3_results.json: Full Tier 1 + Tier 3 results
    - stdout.log / stderr.log (captured by JobManager)
"""

import sys
import json
import argparse
import asyncio
import logging
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def write_progress(job_dir: Path, stage: str, current: int, total: int = 100):
    """
    Write progress for JobManager to monitor.

    This enables real-time progress streaming via MCP notifications,
    eliminating the need for continuous polling.

    Args:
        job_dir: Job directory path
        stage: Description of current stage
        current: Current progress (0-100)
        total: Total progress points (default 100)
    """
    progress_file = job_dir / "progress.json"
    try:
        with open(progress_file, 'w') as f:
            json.dump({
                "stage": stage,
                "current": current,
                "total": total,
                "timestamp": time.time()
            }, f)
    except Exception as e:
        logger.warning(f"Failed to write progress: {e}")


def convert_to_dict(obj):
    """Recursively convert dataclasses and Pydantic models to plain dicts/lists."""
    from pydantic import BaseModel
    from dataclasses import fields

    if isinstance(obj, BaseModel):
        return {k: convert_to_dict(v) for k, v in obj.model_dump().items()}
    if hasattr(obj, "__dataclass_fields__"):
        return {field.name: convert_to_dict(getattr(obj, field.name)) for field in fields(obj)}
    if isinstance(obj, dict):
        return {k: convert_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [convert_to_dict(item) for item in obj]
    return obj


async def run_tier3_costing(job_dir: Path):
    """
    Run Tier 1 + Tier 3 WaterTAP economic costing.

    Args:
        job_dir: Job directory containing params.json

    Returns:
        Exit code (0 for success, 1 for error)
    """
    from tools.heuristic_sizing import heuristic_sizing
    from tools.watertap_costing import cost_degasser_system_async

    params_file = job_dir / "params.json"
    output_file = job_dir / "tier3_results.json"

    if not params_file.exists():
        logger.error(f"params.json not found in {job_dir}")
        return 1

    try:
        # Load parameters
        with open(params_file) as f:
            params = json.load(f)

        logger.info(f"Running Tier 3 costing for {params.get('application', 'unknown')}")
        write_progress(job_dir, "Loading WaterTAP/Pyomo (this takes ~10-20 seconds first time)", 5)

        # Extract Tier 1 parameters
        tier1_params = {
            'application': params['application'],
            'water_flow_rate_m3_h': params['water_flow_rate_m3_h'],
            'inlet_concentration_mg_L': params['inlet_concentration_mg_L'],
            'outlet_concentration_mg_L': params['outlet_concentration_mg_L'],
            'air_water_ratio': params.get('air_water_ratio', 30.0),
            'temperature_c': params.get('temperature_c', 25.0),
            'packing_id': params.get('packing_id'),
            'henry_constant_25C': params.get('henry_constant_25C'),
            'water_ph': params.get('water_ph'),
            'water_chemistry_json': params.get('water_chemistry_json'),
            'include_blower_sizing': params.get('include_blower_sizing', True),
            'blower_efficiency_override': params.get('blower_efficiency_override'),
            'motor_efficiency': params.get('motor_efficiency', 0.92)
        }

        # Extract Tier 3 specific parameters
        packing_type = params.get('packing_type', 'plastic_pall')

        # Run Tier 1 heuristic sizing
        logger.info("Running Tier 1 heuristic sizing...")
        write_progress(job_dir, "Running Tier 1 heuristic sizing", 20)
        tier1_outcome = await heuristic_sizing(**tier1_params)

        # Convert Tier 1 to dict
        tier1_dict = convert_to_dict(tier1_outcome)
        write_progress(job_dir, "Tier 1 complete, starting WaterTAP costing", 35)

        # Run Tier 3 WaterTAP costing
        logger.info("Running Tier 3 WaterTAP economic costing...")
        write_progress(job_dir, "Building Pyomo costing model", 40)
        tier3_result = await cost_degasser_system_async(
            tier1_outcome=tier1_outcome,
            tier2_result=None,
            application=params['application'],
            packing_type=packing_type
        )

        write_progress(job_dir, "Finalizing results", 90)

        # Combine results
        result = tier1_dict
        result['tier3'] = convert_to_dict(tier3_result)

        # Write output
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, allow_nan=False)

        # Extract key metrics for summary
        total_capex = tier3_result.total_capex if hasattr(tier3_result, 'total_capex') else result['tier3'].get('total_capex', 0)
        total_opex = tier3_result.total_annual_opex if hasattr(tier3_result, 'total_annual_opex') else result['tier3'].get('total_annual_opex', 0)

        logger.info(f"Tier 3 complete: CAPEX=${total_capex:,.0f}, Annual OPEX=${total_opex:,.0f}")
        write_progress(job_dir, f"Complete: CAPEX=${total_capex:,.0f}, OPEX=${total_opex:,.0f}/yr", 100)

        return 0

    except Exception as e:
        import traceback
        logger.error(f"Tier 3 costing failed: {e}")
        error_result = {
            "status": "error",
            "message": f"Tier 3 costing failed: {str(e)}",
            "traceback": traceback.format_exc()
        }
        with open(output_file, 'w') as f:
            json.dump(error_result, f, indent=2)
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Tier 3 WaterTAP Economic Costing CLI Runner'
    )
    parser.add_argument(
        '--job-dir',
        required=True,
        help='Job directory containing params.json'
    )

    args = parser.parse_args()
    job_dir = Path(args.job_dir)

    if not job_dir.exists():
        logger.error(f"Job directory does not exist: {job_dir}")
        return 1

    return asyncio.run(run_tier3_costing(job_dir))


if __name__ == "__main__":
    sys.exit(main())
