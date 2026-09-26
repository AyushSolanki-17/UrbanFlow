# Foundation catalog / writer / Trino compatibility spike — 2026-09-26

[Roadmap](../roadmap.md) · [Local deployment](../architecture/local.md) · [Contracts](../data-model/contracts.md)

**Status:** proven shared-catalog path for both file and S3 warehouses. Tiny Iceberg tables written with PyIceberg are readable through Trino via the same PostgreSQL JDBC catalog. This closes the open question from the 2026-09-26 local SQLite/file spike.

## Candidate selection

| Component      | Selected candidate          | Version / image                                                                                                                                                                    | Rationale                                                                                                                                                                                                                                                                                                                                                                                  |
| -------------- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Writer         | PyIceberg + PyArrow         | pyiceberg 0.12.0, pyarrow 25.0.1                                                                                                                                                   | Pure-Python, no Spark JVM required for Stage 1. Produces standard Iceberg v2 metadata/parquet files that Trino, Spark, DuckDB can read. Matches the earlier local spike so upgrade risk is minimal.                                                                                                                                                                                        |
| Shared catalog | PostgreSQL SQL/JDBC catalog | Postgres 16 (postgres:latest 18.6 on host), catalog_name `spike_pg`, sql type `postgresql+psycopg2://` (PyIceberg) / `iceberg.jdbc-catalog.*` with `org.postgresql.Driver` (Trino) | Reuses the existing `urbanflow` Postgres instance, no extra catalog server. Both engines share the same `iceberg_tables` / `iceberg_namespace_properties` tables. Matches Trino's supported `jdbc` catalog type; avoids deploying Polaris/Nessie for the minimal spike. REST (Polaris) remains a candidate for later if row-level credential vending or multi-catalog isolation is needed. |
| Storage (file) | Local filesystem warehouse  | `file:///…/.local/spike-iceberg/warehouse` (host absolute path) mounted read-only into Trino at the same absolute path **and** its `/tmp`-prefixed variant                         | Proves catalog coordination with minimal overhead.                                                                                                                                                                                                                                                                                                                                         |
| Storage (S3)   | S3 warehouse via S3Mock     | `s3://warehouse` (Adobe S3Mock `adobe/s3mock:latest` at `s3mock:9090` / `localhost:9090`), buckets `warehouse,lakehouse` created via S3 API                                        | Proves same JDBC catalog with object storage. Uses `fs.native-s3.enabled=true` + `s3.endpoint`/`s3.path-style-access` in Trino and `s3.endpoint`/`s3.access-key-id`/`s3.secret-access-key` in PyIceberg. Validated 2026-09-26 — see S3 variant below.                                                                                                                                      |
| Query engine   | Trino                       | trinodb/trino:476 (client trino 0.340.0)                                                                                                                                           | Target analytical query path from platform.md. `iceberg` connector with `jdbc` catalog and `fs.native-local.enabled=true` for local files.                                                                                                                                                                                                                                                 |
| DuckDB         | Local inspection baseline   | DuckDB 1.x (via `read_parquet` or `iceberg` extension)                                                                                                                             | No services required. Reads the same Parquet data files under `warehouse/spike/pg_tiny/data/*.parquet` for quick local checks; not a catalog replacement.                                                                                                                                                                                                                                  |

Rejected / deferred:

- **SQLite file catalog** — proven for isolated local write/read, but not shared (Trino would need a shared filesystem DB file and a JDBC driver that Trino does not bundle).
- **REST/ Polaris / Nessie** — heavier operational cost for the minimal spike; keep as Stage 2 option when credential vending or multi-engine REST is required.
- **Spark writer** — deferred to Stage 2 Bronze → Silver; not needed to validate the catalog/query path.

## What was proven

1. **Write path:** `src/urbanflow/lakehouse/catalog.py:load_spike_catalog` loads a `sql` catalog backed by PostgreSQL and a file warehouse. `src/urbanflow/lakehouse/writer.py:write_tiny_table` creates namespace `spike`, drops/creates `spike.pg_tiny` with schema `(pickup_zone: int32, fare_amount: double)` and appends 2 rows `[(10,5.0),(20,6.0)]`.
2. **PyIceberg readback:** `table.scan().to_arrow()` returns 2 rows with identical schema.
3. **Trino read:** same table via `iceberg.spike.pg_tiny`:
   - `SHOW SCHEMAS FROM iceberg` includes `spike`.
   - `SHOW TABLES FROM iceberg.spike` lists `pg_tiny`.
   - `DESCRIBE iceberg.spike.pg_tiny` → `(pickup_zone integer, fare_amount double)` (Trino maps int32→integer, double→double; row count and types match).
   - `SELECT count(*) FROM iceberg.spike.pg_tiny` → 2.
   - `SELECT pickup_zone, fare_amount FROM iceberg.spike.pg_tiny ORDER BY pickup_zone` → `[[10,5.0],[20,6.0]]`.

The run was executed from the repository root with the venv Python:

```sh
.venv/bin/python scripts/spike_iceberg_trino.py
```

Output (2026-09-26):

```text
== Stage 1 spike: PyIceberg -> PostgreSQL JDBC catalog -> Trino ==
pyiceberg=0.12.0 pyarrow=25.0.1 trino=0.340.0
warehouse=/Users/ayushsolanki/Desktop/Projects/UrbanFlow/.local/spike-iceberg/warehouse uri=file:///Users/ayushsolanki/Desktop/Projects/UrbanFlow/.local/spike-iceberg/warehouse
catalog=sql type, uri=postgresql+psycopg2://urbanflow@postgres:5432/urbanflow, catalog_name=spike_pg
written table=('spike', 'pg_tiny') location=file:///…/warehouse/spike/pg_tiny rows=2
pyiceberg readback ok rows=2 schema=pickup_zone: int32
fare_amount: double
trino DESCRIBE: [['pickup_zone', 'integer', '', ''], ['fare_amount', 'double', '', '']]
trino SELECT: [[10, 5.0], [20, 6.0]]
trino count: 2
SUCCESS: PyIceberg write is readable via Trino (schema and row count match).
```

## Configuration evidence

**Warehouse (file)** (ignored, `.local/spike-iceberg/warehouse`):

- Host path mounted read-only into Trino at the same absolute path **and** at `file:///tmp` + same path because Trino's `LocalInputFile` prefixes local paths with `/tmp`. This is the only Trino-specific mount quirk for `file://` warehouses; S3 warehouses do not need it.

**Trino catalog** (`docker/trino/catalog/iceberg.properties`):

```properties
connector.name=iceberg
iceberg.catalog.type=jdbc
iceberg.jdbc-catalog.driver-class=org.postgresql.Driver
iceberg.jdbc-catalog.connection-url=jdbc:postgresql://postgres:5432/urbanflow
iceberg.jdbc-catalog.connection-user=urbanflow
iceberg.jdbc-catalog.connection-password=${ENV:POSTGRES_PASSWORD}
iceberg.jdbc-catalog.catalog-name=spike_pg
iceberg.jdbc-catalog.default-warehouse-dir=file:///Users/ayushsolanki/Desktop/Projects/UrbanFlow/.local/spike-iceberg/warehouse
iceberg.file-format=PARQUET
fs.native-local.enabled=true
fs.native-s3.enabled=true
s3.endpoint=http://s3mock:9090
s3.path-style-access=true
s3.aws-access-key=test
s3.aws-secret-key=test
s3.region=us-east-1
```

`compose.yaml` passes `POSTGRES_PASSWORD` from `.env` into the Trino container for `${ENV:...}` substitution.

**Compose** (`compose.yaml`): `postgres` (port 5432) + `s3mock: adobe/s3mock:latest` (ports 9090/9191, `initialBuckets: warehouse,lakehouse`, healthcheck via `wget`) + `trino:476` (port 8080, depends_on postgres & s3mock healthy, mounts file warehouse at both absolute and `/tmp`-prefixed paths).

**DuckDB baseline:** `duckdb.sql("SELECT * FROM read_parquet('.local/spike-iceberg/warehouse/spike/pg_tiny/data/*.parquet')")` returns the same 2 rows. With the DuckDB Iceberg extension, `SELECT * FROM iceberg_scan('…/warehouse/spike/pg_tiny')` also works against the same metadata.

### S3 variant (2026-09-26)

Same JDBC catalog `spike_pg` (so file and S3 tables coexist in `iceberg_tables`), warehouse `s3://warehouse`.

_Writer:_ `src/urbanflow/lakehouse/catalog.py:load_spike_s3_catalog` with `s3.endpoint=http://localhost:9090`, `s3.access-key-id=test`, `s3.secret-access-key=test`, `warehouse=s3://warehouse`.

_Trino:_ same `iceberg.properties` above with `fs.native-s3.enabled=true` and `s3.endpoint=http://s3mock:9090`.

Run:

```sh
.venv/bin/python scripts/spike_iceberg_s3.py
```

Output (2026-09-26):

```text
== S3 spike: PyIceberg (S3) -> PostgreSQL JDBC catalog -> Trino (S3) ==
pyiceberg=0.12.0 pyarrow=25.0.1 trino=0.340.0
catalog warehouse=s3://warehouse endpoint=http://localhost:9090
written table=('spike_s3', 'tiny_s3') location=s3://warehouse/spike_s3/tiny_s3 rows=2
pyiceberg readback ok rows=2
trino DESCRIBE: [['pickup_zone', 'integer', '', ''], ['fare_amount', 'double', '', '']]
trino SELECT: [[30, 9.5], [40, 12.0]]
trino count: 2
SUCCESS: S3 write readable via Trino.
```

Buckets are created via S3 API (`boto3` `create_bucket`) on first run; S3Mock stores them in `/tmp/s3mockFileStore` (ephemeral, <1 MB spike). File and S3 tables share the same `iceberg` catalog (`spike_pg`) and PostgreSQL backend.

## Resource and limits

Both spikes write <1 MB and use the existing 8–10 GB RAM budget. Warehouse and catalog live under `.local` (file) and S3Mock `/tmp` (ephemeral) and are not committed. No Spark, Flink, or Kafka is required. The S3Mock variant validates the target object-storage path; a MinIO `s3://warehouse` deployment uses identical `s3.endpoint`/`s3.path-style-access` settings with `MINIO_ROOT_USER`/`PASSWORD` credentials.

## What remains

- First analytical table (`raw_yellow_trips` → `zone_hour_demand`) using this writer/catalog path (file and S3).
- History/latest refresh semantics and quarantine/reconciliation for the published table.
