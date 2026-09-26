#!/usr/bin/env python3
"""Stage 1 S3/MinIO (S3Mock) spike — same catalog, S3 warehouse.

Writer: PyIceberg 0.12.0 + PyArrow 25.0.1 via S3FileIO to S3Mock
Catalog: PostgreSQL JDBC shared catalog (spike_pg) — same as file spike
Warehouse: s3://warehouse (S3Mock at http://localhost:9090)
Query: Trino 476 with fs.native-s3.enabled + s3.endpoint http://s3mock:9090
"""

import sys

from urbanflow.lakehouse.catalog import load_spike_s3_catalog


def main() -> int:
    print("== S3 spike: PyIceberg (S3) -> PostgreSQL JDBC catalog -> Trino (S3) ==")
    import importlib.metadata as md

    print(
        f"pyiceberg={md.version('pyiceberg')} pyarrow={md.version('pyarrow')} "  # noqa: E501
        f"trino={md.version('trino')}"
    )

    catalog = load_spike_s3_catalog()
    print("catalog warehouse=s3://warehouse endpoint=http://localhost:9090")

    # Ensure S3 buckets exist (S3Mock is ephemeral; create via boto3 if missing)
    try:
        import boto3
        from botocore.exceptions import ClientError

        s3 = boto3.client(
            "s3",
            endpoint_url="http://localhost:9090",
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name="us-east-1",
        )
        for bucket in ("warehouse", "lakehouse"):
            try:
                s3.head_bucket(Bucket=bucket)
            except ClientError:
                s3.create_bucket(Bucket=bucket)
                print(f"created bucket {bucket}")
    except Exception as exc:  # noqa: BLE001
        print(f"bucket ensure warning: {exc}")

    # Ensure namespace
    try:
        catalog.create_namespace("spike_s3")
    except Exception:
        pass

    import pyarrow as pa

    schema = pa.schema([("pickup_zone", pa.int32()), ("fare_amount", pa.float64())])
    data = pa.table(
        {
            "pickup_zone": pa.array([30, 40], type=pa.int32()),
            "fare_amount": pa.array([9.5, 12.0], type=pa.float64()),
        },
        schema=schema,
    )

    try:
        catalog.drop_table("spike_s3.tiny_s3")
    except Exception:
        pass

    table = catalog.create_table("spike_s3.tiny_s3", schema=data.schema)
    table.append(data)
    print(f"written table={table.name()} location={table.location()} rows={data.num_rows}")

    read = table.scan().to_arrow()
    assert read.num_rows == data.num_rows
    print(f"pyiceberg readback ok rows={read.num_rows}")

    # Trino verification
    try:
        import trino

        conn = trino.dbapi.connect(
            host="localhost", port=8080, catalog="iceberg", schema="spike_s3", user="test"
        )
        cur = conn.cursor()
        cur.execute("DESCRIBE iceberg.spike_s3.tiny_s3")
        print(f"trino DESCRIBE: {cur.fetchall()}")
        cur.execute(
            "SELECT pickup_zone, fare_amount FROM iceberg.spike_s3.tiny_s3 ORDER BY pickup_zone"
        )
        print(f"trino SELECT: {cur.fetchall()}")
        cur.execute("SELECT count(*) FROM iceberg.spike_s3.tiny_s3")
        cnt = cur.fetchall()[0][0]
        print(f"trino count: {cnt}")
        assert cnt == data.num_rows
        print("SUCCESS: S3 write readable via Trino.")
    except Exception as exc:
        print(f"TRINO CHECK FAILED: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
