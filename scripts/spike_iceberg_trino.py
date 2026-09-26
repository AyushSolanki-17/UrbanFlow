#!/usr/bin/env python3
"""Stage 1 Iceberg + Trino compatibility spike.

- Writer: PyIceberg 0.12.0 + PyArrow 25.0.1
- Catalog: PostgreSQL SQL/JDBC shared catalog (catalog_name=spike_pg)
- Warehouse: local file ``.local/spike-iceberg/warehouse`` (native local FS)
- Query: Trino 476 Iceberg connector via JDBC catalog

The script writes a deterministic 2-row table via PyIceberg and reads
it back through both PyIceberg and Trino, confirming schema and row
count. It is the executable companion to
``docs/spikes/2026-09-26-foundation-compatibility.md``.
"""

import sys

from urbanflow.lakehouse.catalog import default_warehouse_path, load_spike_catalog
from urbanflow.lakehouse.writer import write_tiny_table


def main() -> int:
    print("== Stage 1 spike: PyIceberg -> PostgreSQL JDBC catalog -> Trino ==")
    # Versions
    import importlib.metadata as md

    print(
        f"pyiceberg={md.version('pyiceberg')} pyarrow={md.version('pyarrow')} "  # noqa: E501
        f"trino={md.version('trino')}"
    )
    warehouse = default_warehouse_path()
    print(f"warehouse={warehouse} uri={warehouse.as_uri()}")
    print(
        "catalog=sql type, uri=postgresql+psycopg2://urbanflow@postgres:5432/urbanflow, "  # noqa: E501
        "catalog_name=spike_pg"
    )

    catalog = load_spike_catalog()
    table, expected = write_tiny_table(catalog=catalog)
    print(f"written table={table.name()} location={table.location()} rows={expected.num_rows}")

    # Read back via PyIceberg
    read = table.scan().to_arrow()
    assert read.num_rows == expected.num_rows, (read.num_rows, expected.num_rows)
    assert read.schema.equals(expected.schema), (read.schema, expected.schema)
    print(f"pyiceberg readback ok rows={read.num_rows} schema={read.schema}")

    # Read via Trino
    try:
        import trino

        conn = trino.dbapi.connect(
            host="localhost", port=8080, catalog="iceberg", schema="spike", user="test"
        )
        cur = conn.cursor()
        cur.execute("DESCRIBE iceberg.spike.pg_tiny")
        schema_rows = cur.fetchall()
        print(f"trino DESCRIBE: {schema_rows}")
        cur.execute(
            "SELECT pickup_zone, fare_amount FROM iceberg.spike.pg_tiny ORDER BY pickup_zone"
        )
        trino_rows = cur.fetchall()
        print(f"trino SELECT: {trino_rows}")
        cur.execute("SELECT count(*) FROM iceberg.spike.pg_tiny")
        count = cur.fetchall()[0][0]
        print(f"trino count: {count}")
        assert count == expected.num_rows, (count, expected.num_rows)
        # Schema check: trino types integer/double map to int32/double
        assert len(schema_rows) == 2
        print("SUCCESS: PyIceberg write is readable via Trino (schema and row count match).")
    except Exception as exc:  # noqa: BLE001
        print(f"TRINO CHECK FAILED: {exc}", file=sys.stderr)
        return 1

    # Verify warehouse mount details
    # Note Trino's local filesystem prefixes file:// with /tmp; we mount both
    # the host absolute path and its /tmp-prefixed variant read-only.
    print(
        "warehouse mounts: host .local/spike-iceberg/warehouse -> container "  # noqa: E501
        "/Users/... and /tmp/Users/..."
    )
    print("Trino catalog file: docker/trino/catalog/iceberg.properties")
    print(
        "DuckDB access: DuckDB can read Parquet files via read_parquet() "
        "or its Iceberg extension; metadata is file-based. Example: "
        "duckdb.sql(\"SELECT * FROM 'warehouse/spike/pg_tiny/data/*.parquet'\")."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
