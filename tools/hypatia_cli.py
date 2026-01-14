"""Minimal Hypatia CLI wrapper for local testing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ping", action="store_true", help="Return OK if the CLI is reachable.")
    parser.add_argument("--output", type=str, default=None, help="Path to write a schedule JSON artifact.")
    parser.add_argument("--n-sats", type=int, default=0, help="Number of satellites to emit in the artifact.")
    parser.add_argument("--n-ground", type=int, default=0, help="Number of ground nodes to emit in the artifact.")
    parser.add_argument("--steps", type=int, default=0, help="Number of steps to emit in the artifact.")
    parser.add_argument("--seed", type=int, default=0, help="Seed (unused, placeholder).")
    args = parser.parse_args()

    if args.ping:
        print("OK")
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "steps": [{"edges": []} for _ in range(max(0, int(args.steps)))],
            "sat_nodes": [f"sat-{i}" for i in range(max(0, int(args.n_sats)))],
            "ground_nodes": [f"ground-{i}" for i in range(max(0, int(args.n_ground)))],
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return

    parser.error("No action specified. Use --ping or --output.")


if __name__ == "__main__":
    main()
