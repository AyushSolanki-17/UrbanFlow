"""Command-line entry point for UrbanFlow pipelines."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import psycopg

from urbanflow.config import load_settings
from urbanflow.database import get_metadata_repository
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
    publish = commands.add_parser(
        "publish-yellow-slice",
        help="publish a Yellow Taxi Bronze/Silver/Gold slice to Iceberg",
    )
    publish.add_argument("--config", type=Path, required=True)
    publish.add_argument("--period", required=True, help="source month in YYYY-MM")
    publish.add_argument(
        "--source-path",
        type=Path,
        default=None,
        help=(
            "path to a Yellow Taxi Parquet release; defaults to the "
            "downloaded release for the period"
        ),
    )
    publish.add_argument(
        "--use-s3",
        action="store_true",
        help="write Iceberg tables to S3 (s3://warehouse) instead of the file warehouse",
    )
    publish.add_argument(
        "--limit-rows",
        type=int,
        default=None,
        help="limit the published slice to the first N source rows (keeps local runs small)",
    )
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
    if args.command == "publish-yellow-slice":
        try:
            from urbanflow.lakehouse.taxi import publish_yellow_slice

            # Resolve source_path: explicit or the latest downloaded release.
            source_path = args.source_path
            if source_path is None:
                # Prefer the configured data_dir layout, fallback to source-sample.
                candidate = (
                    settings.data_dir
                    / "bronze"
                    / "raw"
                    / "source=nyc_tlc"
                    / "service=yellow"
                    / f"period={args.period}"
                )
                if candidate.exists():
                    releases = sorted(candidate.glob("release=sha256-*/yellow_tripdata_*.parquet"))
                    if releases:
                        source_path = releases[-1]
                if source_path is None:
                    fallback = (
                        Path("docs")
                        / ".."
                        / ".local"
                        / "source-samples"
                        / "nyc-tlc"
                        / f"yellow_tripdata_{args.period}.parquet"
                    )
                    # Resolve from repo root: the CLI is run from the repo root.
                    repo_fallback = (
                        Path.cwd()
                        / ".local"
                        / "source-samples"
                        / "nyc-tlc"
                        / f"yellow_tripdata_{args.period}.parquet"
                    )
                    if repo_fallback.is_file():
                        source_path = repo_fallback
                    elif fallback.is_file():
                        source_path = fallback
                if source_path is None or not Path(source_path).is_file():
                    parser.exit(
                        1,
                        f"urbanflow: no source file found for period {args.period}; "  # noqa: E501
                        "run download-yellow-taxi first or pass --source-path\n",
                    )
            else:
                source_path = Path(source_path)
                if not source_path.is_file():
                    parser.exit(1, f"urbanflow: source-path does not exist: {source_path}\n")

            # Optionally slice the source to stay within the 20 GB peak.
            if args.limit_rows is not None:
                import pyarrow.parquet as pq

                tmp_slice = Path.cwd() / ".local" / "publish_slice_tmp.parquet"
                tmp_slice.parent.mkdir(parents=True, exist_ok=True)
                # Read just the first N rows for a small deterministic run.
                tbl = pq.read_table(source_path).slice(0, args.limit_rows)
                pq.write_table(tbl, tmp_slice)
                source_path = tmp_slice

            result = publish_yellow_slice(
                args.period,
                source_path,
                use_s3=args.use_s3,
            )
            payload = asdict(result)
            payload.update(
                bronze_table=result.bronze_table,
                silver_table=result.silver_table,
                quarantine_table=result.quarantine_table,
                gold_table=result.gold_table,
                accepted_rows=result.accepted_rows,
                quarantined_rows=result.quarantined_rows,
                gold_rows=result.gold_rows,
                bronze_snapshot_id=result.bronze_snapshot_id,
                silver_snapshot_id=result.silver_snapshot_id,
                gold_snapshot_id=result.gold_snapshot_id,
                gold_schema=result.gold_schema,
            )
            print(json.dumps(payload, indent=2, default=str))
            return 0
        except (OSError, RuntimeError, ValueError, psycopg.Error) as error:
            parser.exit(1, f"urbanflow: publish error: {error}\n")
    try:
        metadata = get_metadata_repository(settings.metadata_database_url)
        result = download_yellow_taxi(
            args.period,
            data_dir=settings.data_dir,
            metadata=metadata,
            refresh=args.refresh,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            working_data_peak_gb=settings.working_data_peak_gb,
        )
    except (OSError, RuntimeError, ValueError, psycopg.Error) as error:
        parser.exit(1, f"urbanflow: download error: {error}\n")
    print(json.dumps(result, indent=2))
    return 0
