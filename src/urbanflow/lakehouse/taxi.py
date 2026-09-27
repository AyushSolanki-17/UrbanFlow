"""Yellow Taxi pipeline from Bronze to Silver to Gold.

Publishes one complete path from a downloaded Parquet release to
hourly demand aggregates, with rejected-row handling, reconciliation
and pinned snapshots. Uses the shared PostgreSQL JDBC catalog so
tables are queryable via Trino.

Tables:
  * ``bronze.raw_yellow_trips`` — source fidelity + provenance
  * ``silver.clean_trips`` — validated rows
  * ``silver.quarantine_yellow_trips`` — rejected rows + reason
  * ``gold.zone_hour_demand`` — ``(city, zone, hour, source_period)`` with counts/averages
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from pyiceberg.exceptions import NoSuchTableError
from pyiceberg.expressions import AlwaysTrue, EqualTo
from pyiceberg.types import StringType, TimestamptzType

from urbanflow.lakehouse.catalog import load_catalog, load_s3_catalog
from urbanflow.lakehouse.rejection_reason import RejectionReason
from urbanflow.lakehouse.slice_result import SliceResult
from urbanflow.lakehouse.table_identifier import (
    CURATED_REJECTED_YELLOW_TRIPS,
    CURATED_VALIDATED_YELLOW_TRIPS,
    LANDING_RAW_YELLOW_TRIPS,
    SERVING_HOURLY_ZONE_DEMAND,
)

# NYC zone IDs are 1..265 for the current taxi-zone vintage.
_NYC_ZONE_MIN, _NYC_ZONE_MAX = 1, 265

# Reasonable passenger counts for Yellow Taxi (driver-reported).
_PASSENGER_MIN, _PASSENGER_MAX = 1, 6
_SOURCE_TIMEZONE = "America/New_York"


def _normalize_source_timestamps(
    values: pa.ChunkedArray | pa.Array,
) -> tuple[pa.Array | pa.ChunkedArray, list[RejectionReason | None]]:
    """Interpret naive TLC wall times in New York and flag DST ambiguity.

    Ambiguous or nonexistent wall times cannot be mapped to one real instant
    from the source value alone, so the caller quarantines those rows.
    """
    if values.type.tz is not None:
        normalized = values.cast(pa.timestamp("us", tz="UTC"))
        return normalized, [None] * len(values)

    earliest = pc.assume_timezone(
        values, _SOURCE_TIMEZONE, ambiguous="earliest", nonexistent="earliest"
    )
    latest = pc.assume_timezone(values, _SOURCE_TIMEZONE, ambiguous="latest", nonexistent="latest")
    earliest_local = pc.local_timestamp(earliest).to_pylist()
    latest_local = pc.local_timestamp(latest).to_pylist()
    distinct_instants = pc.not_equal(earliest, latest).to_pylist()
    source_values = values.to_pylist()
    reasons: list[RejectionReason | None] = []
    for source, local_early, local_late, distinct in zip(
        source_values, earliest_local, latest_local, distinct_instants, strict=True
    ):
        if source is None:
            reasons.append(None)
        elif local_early != source or local_late != source:
            reasons.append(RejectionReason.NONEXISTENT_LOCAL_TIMESTAMP)
        elif distinct:
            reasons.append(RejectionReason.AMBIGUOUS_LOCAL_TIMESTAMP)
        else:
            reasons.append(None)
    return earliest.cast(pa.timestamp("us", tz="UTC")), reasons


def split_validated_and_rejected(
    table: pa.Table,
) -> tuple[pa.Table, pa.Table]:
    """Split ``table`` into validated and rejected rows.

    Validation rules (per contracts.md Quality):
    * ``tpep_pickup_datetime`` and ``tpep_dropoff_datetime`` not null
    * ``tpep_dropoff_datetime`` >= ``tpep_pickup_datetime``
    * ``PULocationID`` / ``DOLocationID`` in 1..265 when not null
    * ``trip_distance`` and ``fare_amount`` >= 0
    * ``passenger_count`` in 1..6 when not null

    Returns:
        Tuple of ``(validated, rejected)`` where rejected has an extra
        ``rejection_reason`` column of type :class:`RejectionReason`.
    """
    n = table.num_rows
    if n == 0:
        empty_rejected = table.append_column("rejection_reason", pa.array([], type=pa.string()))
        return table, empty_rejected

    pickup = table["tpep_pickup_datetime"]
    dropoff = table["tpep_dropoff_datetime"]
    pu = table["PULocationID"]
    do = table["DOLocationID"]
    distance = table["trip_distance"]
    fare = table["fare_amount"]
    passenger = table["passenger_count"] if "passenger_count" in table.column_names else None
    pickup_utc, pickup_time_issues = _normalize_source_timestamps(pickup)
    dropoff_utc, dropoff_time_issues = _normalize_source_timestamps(dropoff)

    reasons: list[RejectionReason | None] = [None] * n

    for i in range(n):
        if pickup[i].as_py() is None or dropoff[i].as_py() is None:
            reasons[i] = RejectionReason.MISSING_TIMESTAMPS
            continue
        if pickup_time_issues[i] is not None:
            reasons[i] = pickup_time_issues[i]
            continue
        if dropoff_time_issues[i] is not None:
            reasons[i] = dropoff_time_issues[i]
            continue
        pu_pick = pickup_utc[i].as_py()
        pu_drop = dropoff_utc[i].as_py()
        if pu_drop < pu_pick:
            reasons[i] = RejectionReason.DROPOFF_BEFORE_PICKUP
            continue
        pu_val = pu[i].as_py()
        do_val = do[i].as_py()
        if pu_val is not None and not (_NYC_ZONE_MIN <= pu_val <= _NYC_ZONE_MAX):
            reasons[i] = RejectionReason.INVALID_PICKUP_ZONE
            continue
        if do_val is not None and not (_NYC_ZONE_MIN <= do_val <= _NYC_ZONE_MAX):
            reasons[i] = RejectionReason.INVALID_DROPOFF_ZONE
            continue
        dist = distance[i].as_py()
        if dist is not None and dist < 0:
            reasons[i] = RejectionReason.NEGATIVE_DISTANCE
            continue
        fare_v = fare[i].as_py()
        if fare_v is not None and fare_v < 0:
            reasons[i] = RejectionReason.NEGATIVE_FARE
            continue
        if passenger is not None:
            pc_val = passenger[i].as_py()
            if pc_val is not None and not (_PASSENGER_MIN <= pc_val <= _PASSENGER_MAX):
                reasons[i] = RejectionReason.INVALID_PASSENGER_COUNT
                continue

    mask_validated = [r is None for r in reasons]
    mask_rejected = [r is not None for r in reasons]

    if any(mask_rejected):
        rejected_indices = [i for i, m in enumerate(mask_rejected) if m]
        rejected_reasons: list[str | None] = [
            str(reasons[i]) if reasons[i] is not None else None for i in rejected_indices
        ]
        rejected_table = table.take(rejected_indices)
        rejected_table = rejected_table.append_column(
            "rejection_reason", pa.array(rejected_reasons, type=pa.string())
        )
    else:
        rejected_table = table.slice(0, 0).append_column(
            "rejection_reason", pa.array([], type=pa.string())
        )

    if all(mask_validated):
        validated_indices = list(range(n))
        validated = table
    elif any(mask_validated):
        validated_indices = [i for i, m in enumerate(mask_validated) if m]
        validated = table.take(validated_indices)
    else:
        validated_indices = []
        validated = table.slice(0, 0)

    index_array = pa.array(validated_indices, type=pa.int64())
    validated = _append_or_replace(validated, "pickup_at_utc", pickup_utc.take(index_array))
    validated = _append_or_replace(validated, "dropoff_at_utc", dropoff_utc.take(index_array))

    return validated, rejected_table


def _append_or_replace(table: pa.Table, name: str, values: pa.Array | pa.ChunkedArray) -> pa.Table:
    """Add a derived field or replace an existing field with the same name."""
    index = table.schema.get_field_index(name)
    if index < 0:
        return table.append_column(name, values)
    return table.set_column(index, name, values)


def _quarantine_table(table: pa.Table) -> tuple[pa.Table, pa.Table]:
    """Backward-compatible alias that returns ``quarantine_reason`` column.

    Old callers expect ``quarantine_reason`` and ``invalid_PULocationID``
    style strings. This wrapper translates the new typed output for
    compatibility.
    """
    validated, rejected = split_validated_and_rejected(table)
    # Translate new column/reason strings to legacy values for compat.
    if "rejection_reason" in rejected.column_names:
        reasons = rejected["rejection_reason"].to_pylist()
        legacy = [
            r.replace("invalid_pickup_zone", "invalid_PULocationID").replace(
                "invalid_dropoff_zone", "invalid_DOLocationID"
            )
            if r is not None
            else None
            for r in reasons
        ]
        # Replace column name
        idx = rejected.schema.get_field_index("rejection_reason")
        rejected = rejected.set_column(idx, "quarantine_reason", pa.array(legacy, type=pa.string()))
    elif "quarantine_reason" not in rejected.column_names and rejected.num_rows == 0:
        # Ensure empty case has legacy column
        rejected = rejected.append_column("quarantine_reason", pa.array([], type=pa.string()))
    return validated, rejected


def build_hourly_zone_demand(validated: pa.Table) -> pa.Table:
    """Aggregate ``validated`` trips to ``gold.zone_hour_demand`` grain.

    Business grain is ``(city, zone, hour)`` where hour is pickup hour
    truncated to UTC. ``source_period`` is retained for period-scoped refreshes.
    Measures: trip_count, avg_distance, avg_fare, sum_fare.
    """
    if validated.num_rows == 0:
        return pa.table(
            {
                "city": pa.array([], type=pa.string()),
                "zone": pa.array([], type=pa.int32()),
                "hour": pa.array([], type=pa.timestamp("us", tz="UTC")),
                "trip_count": pa.array([], type=pa.int64()),
                "avg_distance": pa.array([], type=pa.float64()),
                "avg_fare": pa.array([], type=pa.float64()),
                "sum_fare": pa.array([], type=pa.float64()),
                "source_period": pa.array([], type=pa.string()),
            }
        )

    city = pa.array(["NYC"] * validated.num_rows, type=pa.string())
    zone = validated["PULocationID"].cast(pa.int32())
    pickup_utc = (
        validated["pickup_at_utc"]
        if "pickup_at_utc" in validated.column_names
        else _normalize_source_timestamps(validated["tpep_pickup_datetime"])[0]
    )
    try:
        hour = pc.floor_temporal(pickup_utc, 60 * 60, "s")
    except Exception:
        py_hours: list[datetime | None] = []
        for v in pickup_utc.to_pylist():
            if v is None:
                py_hours.append(None)
            else:
                py_hours.append(v.replace(minute=0, second=0, microsecond=0))
        hour = pa.array(py_hours, type=pa.timestamp("us", tz="UTC"))

    tbl = pa.table(
        {
            "city": city,
            "zone": zone,
            "hour": hour,
            "source_period": validated["source_period"]
            if "source_period" in validated.column_names
            else pa.nulls(validated.num_rows, type=pa.string()),
            "trip_distance": validated["trip_distance"].cast(pa.float64()),
            "fare_amount": validated["fare_amount"].cast(pa.float64()),
        }
    )

    grouped = tbl.group_by(["city", "zone", "hour", "source_period"]).aggregate(
        [
            ("trip_distance", "count"),
            ("trip_distance", "mean"),
            ("fare_amount", "mean"),
            ("fare_amount", "sum"),
        ]
    )
    renamed = grouped.rename_columns(
        {
            "trip_distance_count": "trip_count",
            "trip_distance_mean": "avg_distance",
            "fare_amount_mean": "avg_fare",
            "fare_amount_sum": "sum_fare",
        }
    )
    return renamed.select(
        [
            "city",
            "zone",
            "hour",
            "trip_count",
            "avg_distance",
            "avg_fare",
            "sum_fare",
            "source_period",
        ]
    )


# Backward-compatible alias for the previous gold terminology.
_gold_aggregate = build_hourly_zone_demand


def _ensure_namespace(catalog: Any, namespace: str) -> None:
    try:
        catalog.create_namespace(namespace)
    except Exception:
        pass


def _write_iceberg_table(
    catalog: Any, identifier: str, data: pa.Table, *, period: str, legacy_periods: set[str]
) -> Any:
    """Replace one source period while retaining all other published periods."""
    try:
        table = catalog.load_table(identifier)
    except NoSuchTableError:
        namespace = identifier.split(".")[0]
        _ensure_namespace(catalog, namespace)
        table = catalog.create_table(identifier, schema=data.schema)
        if data.num_rows:
            table.append(data)
    else:
        table = _add_legacy_period_column(catalog, table, identifier, legacy_periods)
        matching = table.scan(
            row_filter=EqualTo("source_period", period), selected_fields=["source_period"]
        ).to_arrow()
        if matching.num_rows:
            table.overwrite(
                data,
                overwrite_filter=EqualTo("source_period", period),
                snapshot_properties={"urbanflow.source_period": period},
            )
        elif data.num_rows:
            table.append(data)
    return catalog.load_table(identifier)


def _add_legacy_period_column(
    catalog: Any, table: Any, identifier: str, legacy_periods: set[str]
) -> Any:
    """Evolve old publication schemas and backfill their period labels."""
    field_names = table.schema().column_names
    needs_period_backfill = "source_period" not in field_names
    needs_normalized_times = identifier == str(CURATED_VALIDATED_YELLOW_TRIPS) and any(
        name not in field_names for name in ("pickup_at_utc", "dropoff_at_utc")
    )
    if not needs_period_backfill and not needs_normalized_times:
        return table
    existing = table.scan().to_arrow()
    backfilled = existing
    update = table.update_schema()
    if needs_period_backfill:
        time_column = "hour" if "hour" in existing.column_names else "tpep_pickup_datetime"
        if time_column not in existing.column_names:
            raise ValueError(f"cannot infer source_period for legacy table {identifier}")
        fallback = next(iter(legacy_periods)) if len(legacy_periods) == 1 else None
        values = []
        for value in existing[time_column].to_pylist():
            if value is None:
                if fallback is None:
                    raise ValueError(
                        f"cannot safely backfill null timestamps in {identifier}; "
                        "legacy source periods are ambiguous"
                    )
                values.append(fallback)
            elif time_column == "hour" and fallback is not None:
                # The original publisher held one complete source period per table.
                values.append(fallback)
            else:
                values.append(f"{value.year:04d}-{value.month:02d}")
        backfilled = backfilled.append_column("source_period", pa.array(values, type=pa.string()))
        update.add_column("source_period", StringType())
    if needs_normalized_times:
        for name in ("pickup_at_utc", "dropoff_at_utc"):
            if name not in field_names:
                update.add_column(name, TimestamptzType())
                backfilled = backfilled.append_column(
                    name, pa.array([None] * backfilled.num_rows, type=pa.timestamp("us", tz="UTC"))
                )
    update.commit()
    if not needs_period_backfill:
        return catalog.load_table(identifier)
    table = catalog.load_table(identifier)
    table.overwrite(
        backfilled,
        overwrite_filter=AlwaysTrue(),
        snapshot_properties={"urbanflow.operation": "legacy_period_backfill"},
    )
    return catalog.load_table(identifier)


def _existing_source_periods(catalog: Any, identifier: str) -> set[str]:
    """Read or infer period labels for safe one-time schema backfill."""
    try:
        table = catalog.load_table(identifier)
    except NoSuchTableError:
        return set()
    if "source_period" not in table.schema().column_names:
        if "tpep_pickup_datetime" not in table.schema().column_names:
            return set()
        timestamps = table.scan(selected_fields=["tpep_pickup_datetime"]).to_arrow()[
            "tpep_pickup_datetime"
        ]
        return {
            f"{value.year:04d}-{value.month:02d}"
            for value in timestamps.to_pylist()
            if value is not None
        }
    return {
        value
        for value in table.scan(selected_fields=["source_period"])
        .to_arrow()["source_period"]
        .to_pylist()
        if value is not None
    }


def _needs_legacy_period_backfill(catalog: Any, identifiers: tuple[str, ...]) -> bool:
    """Return whether any published table predates period-scoped writes."""
    for identifier in identifiers:
        try:
            table = catalog.load_table(identifier)
        except NoSuchTableError:
            continue
        if "source_period" not in table.schema().column_names:
            return True
    return False


def publish_yellow_slice(
    period: str,
    source_path: Path | str,
    *,
    source_sha256: str | None = None,
    use_s3: bool = False,
    catalog: Any | None = None,
) -> SliceResult:
    """Publish one Yellow Taxi slice from ``source_path``.

    Args:
        period: ``YYYY-MM`` source period (e.g. ``2024-01``).
        source_path: Path to the released Parquet file
            (``bronze/raw/.../yellow_tripdata_YYYY-MM.parquet``).
        source_sha256: SHA-256 of the release; derived if not supplied.
        use_s3: If true, use the S3 warehouse (``s3://warehouse``);
            otherwise the file warehouse.
        catalog: Optional pre-loaded catalog; defaults to the file or
            S3 catalog.

    Returns:
        A :class:`SliceResult` with row counts, snapshot IDs, and lineage
        for the published Bronze/Silver/Gold tables.
    """
    import hashlib

    source_path = Path(source_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"source release not found: {source_path}")
    try:
        parsed_period = datetime.strptime(period, "%Y-%m")
    except ValueError as error:
        raise ValueError("period must use YYYY-MM format") from error
    if parsed_period.strftime("%Y-%m") != period:
        raise ValueError("period must use YYYY-MM format")

    if catalog is None:
        catalog = load_s3_catalog() if use_s3 else load_catalog()

    source_table = pq.read_table(source_path)
    input_rows: int = source_table.num_rows

    if source_sha256 is None:
        h = hashlib.sha256()
        with source_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        source_sha256 = h.hexdigest()

    # Add provenance columns for the landing dataset.
    now = datetime.now(UTC)
    landing_table = source_table.append_column(
        "ingested_at_utc", pa.array([now] * input_rows, type=pa.timestamp("us", tz="UTC"))
    )
    landing_table = landing_table.append_column(
        "source_period", pa.array([period] * input_rows, type=pa.string())
    )
    landing_table = landing_table.append_column(
        "source_sha256", pa.array([source_sha256] * input_rows, type=pa.string())
    )

    # Validated / rejected split.
    # Publish the established quarantine_reason field while exposing the new
    # validated/rejected API to other callers.
    validated, rejected = _quarantine_table(source_table)
    validated_rows: int = validated.num_rows
    rejected_rows: int = rejected.num_rows
    # No stable TLC trip identifier exists; equal-valued rows can be distinct trips.
    # Preserve every source row and count no row-level duplicates as discarded.
    duplicate_rows = 0
    assert validated_rows + rejected_rows + duplicate_rows == input_rows
    rejected = rejected.append_column(
        "source_period", pa.array([period] * rejected_rows, type=pa.string())
    )

    if validated_rows > 0:
        validated_table = validated.append_column(
            "ingested_at_utc",
            pa.array([now] * validated_rows, type=pa.timestamp("us", tz="UTC")),
        )
        validated_table = validated_table.append_column(
            "source_period", pa.array([period] * validated_rows, type=pa.string())
        )
    else:
        validated_table = validated.append_column(
            "ingested_at_utc", pa.array([], type=pa.timestamp("us", tz="UTC"))
        ).append_column("source_period", pa.array([], type=pa.string()))
        validated_table = validated_table.append_column(
            "pickup_at_utc", pa.array([], type=pa.timestamp("us", tz="UTC"))
        ).append_column("dropoff_at_utc", pa.array([], type=pa.timestamp("us", tz="UTC")))

    demand_table = build_hourly_zone_demand(validated_table)

    # Typed Iceberg identifiers (proper business wording).
    landing_id = str(LANDING_RAW_YELLOW_TRIPS)
    validated_id = str(CURATED_VALIDATED_YELLOW_TRIPS)
    rejected_id = str(CURATED_REJECTED_YELLOW_TRIPS)
    demand_id = str(SERVING_HOURLY_ZONE_DEMAND)

    table_ids = (landing_id, validated_id, rejected_id, demand_id)
    legacy_periods = (
        _existing_source_periods(catalog, landing_id)
        if _needs_legacy_period_backfill(catalog, table_ids)
        else set()
    )
    landing_handle = _write_iceberg_table(
        catalog, landing_id, landing_table, period=period, legacy_periods=legacy_periods
    )
    validated_handle = _write_iceberg_table(
        catalog, validated_id, validated_table, period=period, legacy_periods=legacy_periods
    )
    _write_iceberg_table(
        catalog, rejected_id, rejected, period=period, legacy_periods=legacy_periods
    )
    demand_handle = _write_iceberg_table(
        catalog, demand_id, demand_table, period=period, legacy_periods=legacy_periods
    )

    def _snap_id(handle: Any) -> int | None:
        try:
            snap = handle.current_snapshot()
            return snap.snapshot_id if snap is not None else None
        except Exception:
            return None

    manifest: dict[str, Any] = {
        "period": period,
        "source_sha256": source_sha256,
        "source_path": str(source_path),
        "input_rows": input_rows,
        "validated_rows": validated_rows,
        "rejected_rows": rejected_rows,
        "duplicate_rows": duplicate_rows,
        "duplicate_policy": "preserve_source_rows; replace_period_on_republication",
        "demand_rows": demand_table.num_rows,
        "landing_snapshot_id": _snap_id(landing_handle),
        "validated_snapshot_id": _snap_id(validated_handle),
        "demand_snapshot_id": _snap_id(demand_handle),
        "demand_schema": demand_table.schema.names,
        "published_at_utc": now.isoformat().replace("+00:00", "Z"),
        # Backward-compatible keys for readers still expecting medallion names.
        "accepted_rows": validated_rows,
        "quarantined_rows": rejected_rows,
        "gold_rows": demand_table.num_rows,
        "bronze_snapshot_id": _snap_id(landing_handle),
        "silver_snapshot_id": _snap_id(validated_handle),
        "gold_snapshot_id": _snap_id(demand_handle),
        "gold_schema": demand_table.schema.names,
    }
    out_dir = Path(".local") / "lakehouse" / f"period={period}"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "slice_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    return SliceResult(
        period=period,
        source_sha256=source_sha256,
        source_row_count=input_rows,
        landing_table=landing_id,
        validated_table=validated_id,
        rejected_table=rejected_id,
        demand_table=demand_id,
        input_rows=input_rows,
        validated_rows=validated_rows,
        rejected_rows=rejected_rows,
        duplicate_rows=duplicate_rows,
        demand_rows=demand_table.num_rows,
        landing_snapshot_id=manifest["landing_snapshot_id"],
        validated_snapshot_id=manifest["validated_snapshot_id"],
        demand_snapshot_id=manifest["demand_snapshot_id"],
        demand_schema=demand_table.schema.names,
        manifest_path=str(manifest_path),
    )
