"""Validate every integration operation against the public Severn Trent schema.

Run with --schema PATH to use a previously downloaded introspection response.
Only anonymous schema introspection is sent; no account or token is required.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy

from graphql import NoDeprecatedCustomRule, build_client_schema, get_introspection_query, parse, validate
import requests


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path)
    args = parser.parse_args()
    constants = runpy.run_path(str(Path(__file__).resolve().parents[1] / "custom_components/severn_trent/const.py"))
    if args.schema:
        payload = json.loads(args.schema.read_text())
    else:
        response = requests.post(
            constants["API_URL"], json={"query": get_introspection_query()}, timeout=(10, 45),
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError("Public schema introspection failed")
    schema = build_client_schema(payload.get("data", payload))
    failed = False
    for name, operation in constants.items():
        if not name.endswith(("_QUERY", "_MUTATION")):
            continue
        errors = validate(schema, parse(operation))
        print(f"{name}: {'FAIL' if errors else 'PASS'}")
        for error in errors:
            print(error)
        for warning in validate(schema, parse(operation), rules=[NoDeprecatedCustomRule]):
            print(f"  DEPRECATED: {warning.message}")
        failed |= bool(errors)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
