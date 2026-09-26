"""Unit checks for the Stage 1 lakehouse spike helpers.

These tests use an isolated SQLite file warehouse so they do not
require a running Postgres or Trino. The Postgres/shared-catalog path
is exercised by the integration spike ``scripts/spike_iceberg_trino.py``.
"""

from pathlib import Path

import pyarrow as pa
from pyiceberg.catalog import load_catalog


def test_writer_creates_expected_schema_and_rows(tmp_path: Path):
    warehouse = tmp_path / "warehouse"
    warehouse.mkdir()
    catalog = load_catalog(
        "test",
        **{
            "type": "sql",
            "uri": f"sqlite:///{warehouse / 'catalog.db'}",
            "warehouse": warehouse.as_uri(),
        },
    )
    catalog.create_namespace("spike")
    schema = pa.schema([("pickup_zone", pa.int32()), ("fare_amount", pa.float64())])
    data = pa.table(
        {
            "pickup_zone": pa.array([10, 20], type=pa.int32()),
            "fare_amount": pa.array([5.0, 6.0], type=pa.float64()),
        },
        schema=schema,
    )
    table = catalog.create_table("spike.pg_tiny", schema=data.schema)
    table.append(data)
    read = table.scan().to_arrow()
    assert read.num_rows == 2
    assert read.schema.equals(data.schema)
    assert read.column("pickup_zone").to_pylist() == [10, 20]


def test_load_spike_catalog_defaults(tmp_path: Path, monkeypatch):
    from urbanflow.lakehouse.catalog import default_warehouse_path, load_spike_catalog

    # default path is under repo .local, but we can test the helper returns a Path
    p = default_warehouse_path()
    assert p.name == "warehouse"
    assert ".local" in str(p)

    # test that load_spike_catalog creates warehouse dir
    wh = tmp_path / "wh"
    # Use sqlite to avoid needing postgres in unit test
    catalog = load_spike_catalog(
        warehouse=wh, uri=f"sqlite:///{wh / 'catalog.db'}", catalog_name="ut"
    )
    assert wh.exists()
    catalog.create_namespace("ns")
    assert catalog.list_namespaces() == [("ns",)]
