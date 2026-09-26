"""Small developer entry point for the foundation package."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from urbanflow.config import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="urbanflow", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-config", help="validate and display a local TOML profile")
    check.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
    except (OSError, ValueError) as error:
        parser.exit(2, f"urbanflow: configuration error: {error}\n")
    print(json.dumps(asdict(settings), default=str, indent=2))
    return 0
