"""Tests for the Yellow Taxi Bronze/Silver/Gold slice."""

from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

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


def test_publish_slice_via_file_warehouse(tmp_path: Path):
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
    src_path = tmp_path / "yellow.parquet"
    pq.write_table(source, src_path)

    from urbanflow.lakehouse.taxi import publish_yellow_slice

    result = publish_yellow_slice("2024-01", src_path, use_s3=False)
    assert result.input_rows == source.num_rows
    assert result.accepted_rows + result.quarantined_rows == result.input_rows
    assert result.gold_rows >= 1
    assert result.manifest_path is not None
    assert Path(result.manifest_path).is_file()
