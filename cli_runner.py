#!/usr/bin/env python
"""
CLI runner for degasser design tools.

This provides a command-line interface to run Tier 3 costing that bypasses
MCP transport limitations for long-running async operations (~30 sec).

The MCP STDIO transport has client-side timeouts that cause "unknown message ID"
errors when calculations take longer than the client's patience window.
Running via subprocess avoids this issue entirely.
"""

import sys
import json
import argparse
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def run_tier3_costing(
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
    packing_type: str = "plastic_pall"
):
    """Run Tier 1 + Tier 3 economic costing directly (bypassing MCP wrapper)."""
    from tools.heuristic_sizing import heuristic_sizing
    from tools.watertap_costing import cost_degasser_system_async
    from dataclasses import asdict

    try:
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

        # Convert to dict (recursively for nested dataclasses and Pydantic models)
        from dataclasses import fields
        from pydantic import BaseModel

        def convert_to_dict(obj):
            """Recursively convert dataclasses and Pydantic models to plain dicts/lists."""
            if isinstance(obj, BaseModel):
                return {k: convert_to_dict(v) for k, v in obj.model_dump().items()}
            if hasattr(obj, "__dataclass_fields__"):
                return {field.name: convert_to_dict(getattr(obj, field.name)) for field in fields(obj)}
            if isinstance(obj, dict):
                return {k: convert_to_dict(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple, set)):
                return [convert_to_dict(item) for item in obj]
            return obj

        result = convert_to_dict(tier1_outcome)

        # Run Tier 3
        tier3_result = await cost_degasser_system_async(
            tier1_outcome=tier1_outcome,
            tier2_result=None,
            application=application,
            packing_type=packing_type
        )
        # Convert tier3_result to ensure all nested objects are serializable
        result['tier3'] = convert_to_dict(tier3_result)

        # Verify conversion worked by forcing a test serialization first
        try:
            _ = json.dumps(result)
        except TypeError as te:
            # Find the problematic object
            import sys
            sys.stderr.write(f"DEBUG: Serialization test failed: {te}\n")
            sys.stderr.write(f"DEBUG: Result keys: {result.keys()}\n")
            if 'tier3' in result:
                sys.stderr.write(f"DEBUG: Tier3 keys: {result['tier3'].keys()}\n")
            raise

        # Print result as JSON to stdout
        print(json.dumps(result, indent=2))
        return 0

    except Exception as e:
        import traceback
        error_result = {
            "status": "error",
            "message": f"Tier 3 costing failed: {str(e)}",
            "traceback": traceback.format_exc()
        }
        print(json.dumps(error_result, indent=2))
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Degasser Design CLI Runner - Bypasses MCP STDIO timeout for Tier 3'
    )
    parser.add_argument(
        'command',
        choices=['tier3'],
        help='Command to run (currently only tier3 supported)'
    )
    parser.add_argument(
        '--params',
        required=True,
        help='JSON parameters for the calculation'
    )

    args = parser.parse_args()

    if args.command == 'tier3':
        params = json.loads(args.params)
        return asyncio.run(run_tier3_costing(**params))

    return 0


if __name__ == "__main__":
    sys.exit(main())
