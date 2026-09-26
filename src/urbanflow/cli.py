"""Small developer entry point for the foundation package."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import psycopg

from urbanflow.config import load_settings
from urbanflow.database import PostgresMetadataAdapter
from urbanflow.ingestion.sources.nyc_taxi import download_yellow_taxi


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="urbanflow", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-config", help="validate and display a local TOML profile")
    check.add_argument("--config", type=Path, required=True)
    download = commands.add_parser(
        "download-yellow-taxi", help="download one monthly NYC TLC Yellow Taxi Parquet file"
    )
    download.add_argument("--config", type=Path, required=True)
    download.add_argument("--period", required=True, help="source month in YYYY-MM format")
    download.add_argument(
        "--refresh", action="store_true", help="check the source for a correction"
    )
    download.add_argument("--timeout-seconds", type=float, default=60)
    download.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
    except (OSError, ValueError) as error:
        parser.exit(2, f"urbanflow: configuration error: {error}\n")
    if args.command == "check-config":
        display_settings = asdict(settings)
        display_settings["metadata_database_url"] = "<redacted>"
        print(json.dumps(display_settings, default=str, indent=2))
        return 0
    try:
        metadata = PostgresMetadataAdapter(settings.metadata_database_url)
        result = download_yellow_taxi(
            args.period,
            data_dir=settings.data_dir,
            metadata=metadata,
            refresh=args.refresh,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
        )
    except (OSError, RuntimeError, ValueError, psycopg.Error) as error:
        parser.exit(1, f"urbanflow: download error: {error}\n")
    print(json.dumps(result, indent=2))
    return 0
