"""Tests for the Yellow Taxi Bronze/Silver/Gold slice."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from pyiceberg.catalog import load_catalog

from urbanflow.lakehouse.taxi import _gold_aggregate, _quarantine_table


def _ts(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _small_table() -> pa.Table:
    return pa.table(
        {
            "tpep_pickup_datetime": pa.array(
                [
                    _ts("2024-01-01T00:10:00"),
                    _ts("2024-01-01T00:15:00"),
                    _ts("2024-01-01T00:20:00"),
                    None,
                    _ts("2024-01-01T00:30:00"),
                ],
                type=pa.timestamp("us"),
            ),
            "tpep_dropoff_datetime": pa.array(
                [
                    _ts("2024-01-01T00:20:00"),
                    _ts("2024-01-01T00:10:00"),
                    _ts("2024-01-01T00:30:00"),
                    _ts("2024-01-01T00:40:00"),
                    _ts("2024-01-01T00:35:00"),
                ],
                type=pa.timestamp("us"),
            ),
            "PULocationID": pa.array([1, 2, 999, 4, 5], type=pa.int32()),
            "DOLocationID": pa.array([10, 20, 30, 40, 50], type=pa.int32()),
            "trip_distance": pa.array([1.0, 2.0, 3.0, 4.0, -1.0], type=pa.float64()),
            "fare_amount": pa.array([10.0, 20.0, 30.0, 40.0, 50.0], type=pa.float64()),
            "passenger_count": pa.array([2, 2, 2, 2, 2], type=pa.int64()),
        }
    )


def test_quarantine_splits_reasons():
    table = _small_table()
    accepted, quarantined = _quarantine_table(table)
    # Row 0: valid
    # Row 1: dropoff_before_pickup
    # Row 2: invalid PULocationID 999
    # Row 3: missing pickup
    # Row 4: negative distance
    assert accepted.num_rows == 1
    assert quarantined.num_rows == 4
    assert accepted.num_rows + quarantined.num_rows == table.num_rows
    reasons = quarantined["quarantine_reason"].to_pylist()
    assert "dropoff_before_pickup" in reasons
    assert "invalid_PULocationID" in reasons
    assert "missing_pickup_or_dropoff" in reasons
    assert "negative_distance" in reasons


def test_equal_trip_rows_are_preserved_without_guessing_duplicate_identity():
    from urbanflow.lakehouse.taxi import split_validated_and_rejected

    valid = _small_table().slice(0, 1)
    source = pa.concat_tables([valid, valid])
    accepted, rejected = split_validated_and_rejected(source)

    assert accepted.num_rows == 2
    assert rejected.num_rows == 0


def test_source_wall_times_normalize_to_utc_and_dst_edge_times_are_rejected():
    from urbanflow.lakehouse.taxi import split_validated_and_rejected

    source = _small_table().slice(0, 2)
    source = source.set_column(
        source.schema.get_field_index("tpep_pickup_datetime"),
        "tpep_pickup_datetime",
        pa.array(
            [datetime(2024, 11, 3, 1, 30), datetime(2024, 3, 10, 2, 15)],
            type=pa.timestamp("us"),
        ),
    )
    source = source.set_column(
        source.schema.get_field_index("tpep_dropoff_datetime"),
        "tpep_dropoff_datetime",
        pa.array(
            [datetime(2024, 11, 3, 1, 45), datetime(2024, 3, 10, 3, 15)],
            type=pa.timestamp("us"),
        ),
    )
    source = source.set_column(
        source.schema.get_field_index("PULocationID"), "PULocationID", pa.array([1, 2])
    )

    accepted, rejected = split_validated_and_rejected(source)

    assert accepted.num_rows == 0
    assert set(rejected["rejection_reason"].to_pylist()) == {
        "ambiguous_local_timestamp",
        "nonexistent_local_timestamp",
    }


def test_gold_aggregate_counts():
    clean = pa.table(
        {
            "PULocationID": pa.array([1, 1, 2], type=pa.int32()),
            "tpep_pickup_datetime": pa.array(
                [
                    _ts("2024-01-01T00:10:00"),
                    _ts("2024-01-01T00:20:00"),
                    _ts("2024-01-01T01:05:00"),
                ],
                type=pa.timestamp("us"),
            ),
            "trip_distance": pa.array([1.0, 3.0, 2.0], type=pa.float64()),
            "fare_amount": pa.array([10.0, 20.0, 15.0], type=pa.float64()),
        }
    )
    gold = _gold_aggregate(clean)
    assert gold.num_rows == 2  # (zone 1 hour 00, zone 2 hour 01)
    df = gold.to_pydict()
    idx = df["zone"].index(1)
    assert df["trip_count"][idx] == 2
    assert df["sum_fare"][idx] == 30.0
    assert df["hour"][idx] == datetime(2024, 1, 1, 5, tzinfo=UTC)


def _full_source_table() -> pa.Table:
    source = _small_table()
    for col, typ in [
        ("VendorID", pa.int32()),
        ("RatecodeID", pa.int64()),
        ("store_and_fwd_flag", pa.string()),
        ("payment_type", pa.int64()),
        ("extra", pa.float64()),
        ("mta_tax", pa.float64()),
        ("tip_amount", pa.float64()),
        ("tolls_amount", pa.float64()),
        ("improvement_surcharge", pa.float64()),
        ("total_amount", pa.float64()),
        ("congestion_surcharge", pa.float64()),
        ("Airport_fee", pa.float64()),
    ]:
        if col not in source.column_names:
            source = source.append_column(col, pa.array([None] * source.num_rows, type=typ))
    return source


def _shift_period(table: pa.Table, days: int) -> pa.Table:
    for name in ("tpep_pickup_datetime", "tpep_dropoff_datetime"):
        shifted = [
            value + timedelta(days=days) if value is not None else None
            for value in table[name].to_pylist()
        ]
        table = table.set_column(
            table.schema.get_field_index(name), name, pa.array(shifted, type=table[name].type)
        )
    return table


def test_publish_replaces_only_the_requested_period_and_keeps_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = _full_source_table()
    warehouse = tmp_path / "warehouse"
    warehouse.mkdir()
    catalog = load_catalog(
        "test",
        **{
            "type": "sql",
            "uri": f"sqlite:///{tmp_path / 'catalog.db'}",
            "warehouse": warehouse.as_uri(),
        },
    )

    from urbanflow.lakehouse.taxi import publish_yellow_slice

    jan_path = tmp_path / "january.parquet"
    feb_path = tmp_path / "february.parquet"
    correction_path = tmp_path / "january-corrected.parquet"
    pq.write_table(source, jan_path)
    pq.write_table(_shift_period(source, 31), feb_path)
    corrected = source.set_column(
        source.schema.get_field_index("fare_amount"),
        "fare_amount",
        pa.array(
            [
                value + 1 if value is not None else None
                for value in source["fare_amount"].to_pylist()
            ],
            type=pa.float64(),
        ),
    )
    pq.write_table(corrected, correction_path)

    january = publish_yellow_slice("2024-01", jan_path, catalog=catalog)
    february = publish_yellow_slice("2024-02", feb_path, catalog=catalog)
    corrected_january = publish_yellow_slice("2024-01", correction_path, catalog=catalog)
    repeated = publish_yellow_slice("2024-01", correction_path, catalog=catalog)

    assert corrected_january.input_rows == source.num_rows
    assert (
        corrected_january.accepted_rows
        + corrected_january.quarantined_rows
        + corrected_january.duplicate_rows
        == source.num_rows
    )
    assert corrected_january.duplicate_rows == 0
    assert repeated.source_sha256 == corrected_january.source_sha256
    assert corrected_january.source_sha256 != january.source_sha256
    assert february.source_sha256 != january.source_sha256

    from urbanflow.lakehouse.table_identifier import (
        CURATED_REJECTED_YELLOW_TRIPS,
        CURATED_VALIDATED_YELLOW_TRIPS,
        LANDING_RAW_YELLOW_TRIPS,
        SERVING_HOURLY_ZONE_DEMAND,
    )

    landing_id = str(LANDING_RAW_YELLOW_TRIPS)
    validated_id = str(CURATED_VALIDATED_YELLOW_TRIPS)
    rejected_id = str(CURATED_REJECTED_YELLOW_TRIPS)
    demand_id = str(SERVING_HOURLY_ZONE_DEMAND)
    bronze_result = catalog.load_table(landing_id).scan().to_arrow()
    periods = bronze_result["source_period"].to_pylist()
    assert bronze_result.num_rows == source.num_rows * 2
    assert periods.count("2024-01") == source.num_rows
    assert periods.count("2024-02") == source.num_rows
    jan_rows = bronze_result.filter(pa.compute.equal(bronze_result["source_period"], "2024-01"))
    assert set(jan_rows["source_sha256"].to_pylist()) == {corrected_january.source_sha256}

    silver_result = catalog.load_table(validated_id).scan().to_arrow()
    rejected_result = catalog.load_table(rejected_id).scan().to_arrow()
    gold_result = catalog.load_table(demand_id).scan().to_arrow()
    assert silver_result.num_rows == corrected_january.accepted_rows + february.accepted_rows
    assert (
        rejected_result.num_rows == corrected_january.quarantined_rows + february.quarantined_rows
    )
    assert "source_period" in rejected_result.column_names
    assert set(gold_result["source_period"].to_pylist()) == {"2024-01", "2024-02"}
    assert gold_result.num_rows == 2
    retained_gold_snapshots = {
        snapshot.snapshot_id for snapshot in catalog.load_table(demand_id).snapshots()
    }
    assert january.gold_snapshot_id in retained_gold_snapshots
    assert json.loads(Path(corrected_january.manifest_path).read_text())["source_sha256"] == (
        corrected_january.source_sha256
    )
    assert json.loads(Path(repeated.manifest_path).read_text())["duplicate_rows"] == 0


def test_publish_migrates_legacy_schema_and_reconciles_null_quarantine_times(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = _full_source_table()
    warehouse = tmp_path / "warehouse"
    warehouse.mkdir()
    catalog = load_catalog(
        "legacy-test",
        **{
            "type": "sql",
            "uri": f"sqlite:///{tmp_path / 'catalog.db'}",
            "warehouse": warehouse.as_uri(),
        },
    )
    from urbanflow.lakehouse.table_identifier import (
        CURATED_REJECTED_YELLOW_TRIPS,
        CURATED_VALIDATED_YELLOW_TRIPS,
        LANDING_RAW_YELLOW_TRIPS,
        SERVING_HOURLY_ZONE_DEMAND,
    )
    from urbanflow.lakehouse.taxi import _gold_aggregate, _quarantine_table, publish_yellow_slice

    now = datetime.now(UTC)
    bronze = source.append_column(
        "ingested_at_utc", pa.array([now] * source.num_rows, type=pa.timestamp("us", tz="UTC"))
    ).append_column("source_sha256", pa.array(["legacy"] * source.num_rows))
    validated, rejected = _quarantine_table(source)
    validated = validated.drop(["pickup_at_utc", "dropoff_at_utc"])
    validated = validated.append_column(
        "ingested_at_utc",
        pa.array([now] * validated.num_rows, type=pa.timestamp("us", tz="UTC")),
    )
    gold = _gold_aggregate(validated).drop(["source_period"])
    for namespace in ("bronze", "silver", "gold"):
        catalog.create_namespace(namespace)
    for identifier, data in (
        (str(LANDING_RAW_YELLOW_TRIPS), bronze),
        (str(CURATED_VALIDATED_YELLOW_TRIPS), validated),
        (str(CURATED_REJECTED_YELLOW_TRIPS), rejected),
        (str(SERVING_HOURLY_ZONE_DEMAND), gold),
    ):
        catalog.create_table(identifier, schema=data.schema).append(data)

    source_path = tmp_path / "legacy-refresh.parquet"
    pq.write_table(source, source_path)
    result = publish_yellow_slice("2024-01", source_path, catalog=catalog)

    assert result.validated_rows + result.rejected_rows + result.duplicate_rows == source.num_rows
    assert result.rejected_rows == 4
    silver = catalog.load_table(str(CURATED_VALIDATED_YELLOW_TRIPS)).scan().to_arrow()
    rejected_rows = catalog.load_table(str(CURATED_REJECTED_YELLOW_TRIPS)).scan().to_arrow()
    assert "pickup_at_utc" in silver.column_names
    assert "dropoff_at_utc" in silver.column_names
    assert set(silver["source_period"].to_pylist()) == {"2024-01"}
    assert set(rejected_rows["source_period"].to_pylist()) == {"2024-01"}
