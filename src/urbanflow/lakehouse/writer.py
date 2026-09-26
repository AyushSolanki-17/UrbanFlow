"""Tiny Iceberg writer used by the Stage 1 spike.

The writer is intentionally small: it creates a table with a known
schema and a deterministic two-row fixture, appends it, and returns
the row count and schema for Trino verification.
"""

from __future__ import annotations

import pyarrow as pa

from urbanflow.lakehouse.catalog import load_spike_catalog


def write_tiny_table(
    identifier: str = "spike.pg_tiny",
    *,
    catalog=None,
):
    """Create and populate a tiny Iceberg table.

    Args:
        identifier: Fully-qualified ``namespace.table`` name.
        catalog: Optional pre-loaded catalog; defaults to the shared
            spike catalog.

    Returns:
        Tuple of (table, data) where ``table`` is the Iceberg table
        handle and ``data`` is the PyArrow fixture written.
    """
    if catalog is None:
        catalog = load_spike_catalog()

    namespace, _, _ = identifier.partition(".")
    # Ensure namespace exists (idempotent).
    try:
        catalog.create_namespace(namespace)
    except Exception:
        pass

    schema = pa.schema(
        [
            ("pickup_zone", pa.int32()),
            ("fare_amount", pa.float64()),
        ]
    )
    data = pa.table(
        {
            "pickup_zone": pa.array([10, 20], type=pa.int32()),
            "fare_amount": pa.array([5.0, 6.0], type=pa.float64()),
        },
        schema=schema,
    )

    # Recreate table if it exists to keep the spike idempotent.
    try:
        catalog.drop_table(identifier)
    except Exception:
        pass

    table = catalog.create_table(identifier, schema=data.schema)
    table.append(data)
    return table, data
