"""Bronze / Silver / Gold pipeline for Yellow Taxi — Stage 1 analytical slice.

Proves one complete path from a downloaded Parquet release to a
published Gold aggregate, with quarantine/reconciliation and a pinned
snapshot. Uses the same PostgreSQL JDBC catalog as the foundation
spike, so the tables are queryable via Trino.

Grain:
  * Bronze ``bronze.raw_yellow_trips`` — source fidelity, 19 columns + provenance
  * Silver ``silver.clean_trips`` — validated rows
  * Quarantine ``silver.quarantine_yellow_trips`` — rejected rows + reason
  * Gold ``gold.zone_hour_demand`` — ``(city, zone, hour)`` with counts/averages

The pipeline is intentionally small and runs on a deterministic
slice of the January 2024 sample so it fits the 20 GB peak budget.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from urbanflow.lakehouse.catalog import load_spike_catalog, load_spike_s3_catalog

# NYC zone IDs are 1..265 for the current taxi-zone vintage.
_NYC_ZONE_MIN, _NYC_ZONE_MAX = 1, 265

# Reasonable passenger counts for Yellow Taxi (driver-reported).
_PASSENGER_MIN, _PASSENGER_MAX = 1, 6


@dataclass(frozen=True)
class SliceResult:
    """Summary of a published Yellow slice."""

    period: str
    source_sha256: str
    source_row_count: int
    bronze_table: str
    silver_table: str
    quarantine_table: str
    gold_table: str
    input_rows: int
    accepted_rows: int
    quarantined_rows: int
    gold_rows: int
    bronze_snapshot_id: int | None
    silver_snapshot_id: int | None
    gold_snapshot_id: int | None
    gold_schema: list[str]
    manifest_path: str


def _quarantine_table(
    table: pa.Table,
) -> tuple[pa.Table, pa.Table]:
    """Split ``table`` into accepted and quarantined rows.

    Validation rules (per contracts.md Quality):
    * ``tpep_pickup_datetime`` and ``tpep_dropoff_datetime`` not null
    * ``tpep_dropoff_datetime`` >= ``tpep_pickup_datetime``
    * ``PULocationID`` / ``DOLocationID`` in 1..265 when not null
    * ``trip_distance`` and ``fare_amount`` >= 0
    * ``passenger_count`` in 1..6 when not null

    Returns ``(accepted, quarantine)`` where quarantine has an extra
    ``quarantine_reason`` column.
    """
    n = table.num_rows
    if n == 0:
        empty_q = table.append_column("quarantine_reason", pa.array([], type=pa.string()))
        return table, empty_q

    pickup = table["tpep_pickup_datetime"]
    dropoff = table["tpep_dropoff_datetime"]
    pu = table["PULocationID"]
    do = table["DOLocationID"]
    distance = table["trip_distance"]
    fare = table["fare_amount"]
    # passenger_count may be null
    passenger = table["passenger_count"] if "passenger_count" in table.column_names else None

    reasons: list[str | None] = [None] * n

    for i in range(n):
        # Missing timestamps — most critical.
        if pickup[i].as_py() is None or dropoff[i].as_py() is None:
            reasons[i] = "missing_pickup_or_dropoff"
            continue
        pu_pick = pickup[i].as_py()
        pu_drop = dropoff[i].as_py()
        if pu_drop < pu_pick:
            reasons[i] = "dropoff_before_pickup"
            continue
        pu_val = pu[i].as_py()
        do_val = do[i].as_py()
        if pu_val is not None and not (_NYC_ZONE_MIN <= pu_val <= _NYC_ZONE_MAX):
            reasons[i] = "invalid_PULocationID"
            continue
        if do_val is not None and not (_NYC_ZONE_MIN <= do_val <= _NYC_ZONE_MAX):
            reasons[i] = "invalid_DOLocationID"
            continue
        dist = distance[i].as_py()
        if dist is not None and dist < 0:
            reasons[i] = "negative_distance"
            continue
        fare_v = fare[i].as_py()
        if fare_v is not None and fare_v < 0:
            reasons[i] = "negative_fare"
            continue
        if passenger is not None:
            pc_val = passenger[i].as_py()
            if pc_val is not None and not (_PASSENGER_MIN <= pc_val <= _PASSENGER_MAX):
                reasons[i] = "invalid_passenger_count"
                continue

    mask_accepted = [r is None for r in reasons]
    mask_quarantine = [r is not None for r in reasons]

    # Build quarantine table with reason.
    if any(mask_quarantine):
        quarantined_indices = [i for i, m in enumerate(mask_quarantine) if m]
        quarantine_reasons = [reasons[i] for i in quarantined_indices]
        q_table = table.take(quarantined_indices)
        q_table = q_table.append_column(
            "quarantine_reason", pa.array(quarantine_reasons, type=pa.string())
        )
    else:
        q_table = table.slice(0, 0).append_column(
            "quarantine_reason", pa.array([], type=pa.string())
        )

    if all(mask_accepted):
        accepted = table
    elif any(mask_accepted):
        accepted_indices = [i for i, m in enumerate(mask_accepted) if m]
        accepted = table.take(accepted_indices)
    else:
        accepted = table.slice(0, 0)

    return accepted, q_table


def _gold_aggregate(clean: pa.Table) -> pa.Table:
    """Aggregate ``clean`` to ``gold.zone_hour_demand`` grain.

    Grain is ``(city, zone, hour)`` where hour is the pickup hour
    truncated to the hour in UTC (source times are treated as UTC for
    the spike; DST handling is deferred per contracts.md).
    Measures: trip_count, avg_distance, avg_fare, sum_fare.
    """
    if clean.num_rows == 0:
        return pa.table(
            {
                "city": pa.array([], type=pa.string()),
                "zone": pa.array([], type=pa.int32()),
                "hour": pa.array([], type=pa.timestamp("us", tz="UTC")),
                "trip_count": pa.array([], type=pa.int64()),
                "avg_distance": pa.array([], type=pa.float64()),
                "avg_fare": pa.array([], type=pa.float64()),
                "sum_fare": pa.array([], type=pa.float64()),
            }
        )

    # Build arrays for grouping.
    city = pa.array(["NYC"] * clean.num_rows, type=pa.string())
    zone = clean["PULocationID"].cast(pa.int32())
    # Truncate pickup to hour — pyarrow compute floor.
    pickup = clean["tpep_pickup_datetime"]
    # Ensure timestamp is UTC for hour bucketing. Source is naive wall time;
    # for the spike we treat it as UTC and cast.
    if pickup.type.tz is None:
        # Treat naive as UTC by casting (no shift, just label).
        pickup_utc = pickup.cast(pa.timestamp("us", tz="UTC"))
    else:
        pickup_utc = pickup
    # Floor to hour: use pc.floor_temporal or manual via cast?
    # PyArrow 25 has pc.floor_temporal
    try:
        hour = pc.floor_temporal(pickup_utc, 60 * 60, "s")
    except Exception:
        # Fallback: strip minutes/seconds via python
        py_hours = []
        for v in pickup_utc.to_pylist():
            if v is None:
                py_hours.append(None)
            else:
                # v is datetime with tz UTC
                py_hours.append(v.replace(minute=0, second=0, microsecond=0))
        hour = pa.array(py_hours, type=pa.timestamp("us", tz="UTC"))

    tbl = pa.table(
        {
            "city": city,
            "zone": zone,
            "hour": hour,
            "trip_distance": clean["trip_distance"].cast(pa.float64()),
            "fare_amount": clean["fare_amount"].cast(pa.float64()),
        }
    )

    grouped = tbl.group_by(["city", "zone", "hour"]).aggregate(
        [
            ("trip_distance", "count"),
            ("trip_distance", "mean"),
            ("fare_amount", "mean"),
            ("fare_amount", "sum"),
        ]
    )
    # Rename aggregated columns
    # PyArrow names them like trip_distance_count etc.
    renamed = grouped.rename_columns(
        {
            "trip_distance_count": "trip_count",
            "trip_distance_mean": "avg_distance",
            "fare_amount_mean": "avg_fare",
            "fare_amount_sum": "sum_fare",
        }
    )
    # Ensure types
    return renamed


def _ensure_namespace(catalog, namespace: str) -> None:
    try:
        catalog.create_namespace(namespace)
    except Exception:
        pass


def _write_iceberg_table(
    catalog,
    identifier: str,
    data: pa.Table,
    *,
    overwrite: bool = True,
) -> Any:
    """Create or overwrite an Iceberg table and append ``data``."""
    if overwrite:
        try:
            catalog.drop_table(identifier)
        except Exception:
            pass
        ns = identifier.split(".")[0]
        _ensure_namespace(catalog, ns)
        table = catalog.create_table(identifier, schema=data.schema)
    else:
        try:
            table = catalog.load_table(identifier)
        except Exception:
            ns = identifier.split(".")[0]
            _ensure_namespace(catalog, ns)
            table = catalog.create_table(identifier, schema=data.schema)
            table.append(data)
            return table
    if data.num_rows > 0:
        table.append(data)
    return table


def publish_yellow_slice(
    period: str,
    source_path: Path | str,
    *,
    source_sha256: str | None = None,
    use_s3: bool = False,
    catalog=None,
) -> SliceResult:
    """Publish one Yellow Taxi slice from ``source_path``.

    Args:
        period: ``YYYY-MM`` source period (e.g. ``2024-01``).
        source_path: Path to the released Parquet file
            (``bronze/raw/.../yellow_tripdata_YYYY-MM.parquet``).
        source_sha256: SHA-256 of the release; derived if not supplied.
        use_s3: If true, use the S3 warehouse (``s3://warehouse``);
            otherwise the file warehouse.
        catalog: Optional pre-loaded catalog; defaults to the spike
            file or S3 catalog.

    Returns:
        A ``SliceResult`` with row counts, snapshot IDs, and lineage
        for the published Bronze/Silver/Gold tables.
    """
    import hashlib

    source_path = Path(source_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"source release not found: {source_path}")

    if catalog is None:
        catalog = load_spike_s3_catalog() if use_s3 else load_spike_catalog()

    # Load source with PyArrow — bounded slice is fine.
    source_table = pq.read_table(source_path)
    input_rows = source_table.num_rows

    if source_sha256 is None:
        h = hashlib.sha256()
        with source_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        source_sha256 = h.hexdigest()

    # Add provenance columns for Bronze.
    now = datetime.now(UTC)
    bronze_table = source_table.append_column(
        "ingested_at_utc", pa.array([now] * input_rows, type=pa.timestamp("us", tz="UTC"))
    )
    bronze_table = bronze_table.append_column(
        "source_period", pa.array([period] * input_rows, type=pa.string())
    )
    bronze_table = bronze_table.append_column(
        "source_sha256", pa.array([source_sha256] * input_rows, type=pa.string())
    )

    # Quarantine split
    accepted, quarantined = _quarantine_table(source_table)
    accepted_rows = accepted.num_rows
    quarantined_rows = quarantined.num_rows
    # Invariant: accepted + quarantined == input
    assert accepted_rows + quarantined_rows == input_rows

    # For Silver, add same provenance to accepted rows if any.
    if accepted_rows > 0:
        silver_table = accepted.append_column(
            "ingested_at_utc", pa.array([now] * accepted_rows, type=pa.timestamp("us", tz="UTC"))
        )
        silver_table = silver_table.append_column(
            "source_period", pa.array([period] * accepted_rows, type=pa.string())
        )
    else:
        silver_table = accepted

    gold_table = _gold_aggregate(silver_table if accepted_rows > 0 else silver_table)

    # Publish to Iceberg
    bronze_id = "bronze.raw_yellow_trips"
    silver_id = "silver.clean_trips"
    quarantine_id = "silver.quarantine_yellow_trips"
    gold_id = "gold.zone_hour_demand"

    # For the Stage 1 slice proof we overwrite all three so that
    # input_rows == accepted + quarantined remains a checkable invariant
    # per run. Later historical periods can append or partition.
    bronze_handle = _write_iceberg_table(catalog, bronze_id, bronze_table, overwrite=True)
    silver_handle = _write_iceberg_table(catalog, silver_id, silver_table, overwrite=True)
    _write_iceberg_table(catalog, quarantine_id, quarantined, overwrite=True)
    gold_handle = _write_iceberg_table(catalog, gold_id, gold_table, overwrite=True)

    # Snapshot IDs for pinned experiments
    def _snap_id(handle) -> int | None:
        try:
            snap = handle.current_snapshot()
            return snap.snapshot_id if snap is not None else None
        except Exception:
            return None

    # Manifest for first analytical slice
    manifest = {
        "period": period,
        "source_sha256": source_sha256,
        "source_path": str(source_path),
        "input_rows": input_rows,
        "accepted_rows": accepted_rows,
        "quarantined_rows": quarantined_rows,
        "gold_rows": gold_table.num_rows,
        "bronze_snapshot_id": _snap_id(bronze_handle),
        "silver_snapshot_id": _snap_id(silver_handle),
        "gold_snapshot_id": _snap_id(gold_handle),
        "gold_schema": gold_table.schema.names,
        "published_at_utc": now.isoformat().replace("+00:00", "Z"),
    }
    # Write manifest under .local for inspection (not committed)
    from pathlib import Path as _P

    out_dir = _P(".local") / "lakehouse" / f"period={period}"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "slice_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    return SliceResult(
        period=period,
        source_sha256=source_sha256,
        source_row_count=input_rows,
        bronze_table=bronze_id,
        silver_table=silver_id,
        quarantine_table=quarantine_id,
        gold_table=gold_id,
        input_rows=input_rows,
        accepted_rows=accepted_rows,
        quarantined_rows=quarantined_rows,
        gold_rows=gold_table.num_rows,
        bronze_snapshot_id=manifest["bronze_snapshot_id"],
        silver_snapshot_id=manifest["silver_snapshot_id"],
        gold_snapshot_id=manifest["gold_snapshot_id"],
        gold_schema=gold_table.schema.names,
        manifest_path=str(manifest_path),
    )
