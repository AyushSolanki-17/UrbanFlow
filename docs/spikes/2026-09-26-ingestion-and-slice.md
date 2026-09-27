# Reproducible ingestion and first analytical slice — 2026-09-26

[Roadmap](../roadmap.md) · [Contracts](../data-model/contracts.md) · [Local deployment](../architecture/local.md)

**Status:** proven via `venv` (`.venv/bin/python`) with PostgreSQL JDBC catalog `spike_pg`.

## Reproducible ingestion (proof 2)

### What was proven

- Derived TLC URL `https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{period}.parquet` with `YYYY-MM` validation (`src/urbanflow/ingestion/sources/nyc_taxi.py:validate_period`).
- Immutable checksum-addressed landing `data_dir/bronze/raw/source=nyc_tlc/service=yellow/period=YYYY-MM/release=sha256-<digest>/yellow_tripdata_YYYY-MM.parquet` with hard-link reuse and content verification.
- Bounded retries with exponential backoff (`_RETRYABLE_HTTP_CODES`, `max_retries`, `timeout_seconds`) and attempt counts recorded in `ingestion_runs`.
- Atomic publication via `.incoming/<run_id>.part` → `os.link` → manifest.
- `unchanged` fast-path reuses a verified local release without fetching; `--refresh` preserves corrected content as a new immutable release under a new SHA-256.
- Failed downloads are recorded with `status=failed`, `error_message`, and partial files are removed.
- **Resource admission:** `working_data_peak_gb` (decimal GB, 1 GB = 1e9 bytes) is enforced via `_working_data_size_bytes` + `Content-Length` against `peak_bytes` in `src/urbanflow/ingestion/sources/nyc_taxi.py:_fetch`. CLI passes `settings.working_data_peak_gb` (`src/urbanflow/cli.py:42`).
- **Manifest:** `release_dir/manifest.json` with `source_id`, `period`, `sha256`, `byte_count`, `row_count`, `schema`, `completed_at_utc` (best-effort via `pyarrow.parquet`).

### Evidence (unit, via `venv`)

```sh
.venv/bin/python -m pytest tests/unit/test_ingestion.py -v
# 14 passed: repeat is unchanged, refresh preserves correction as new SHA, retries transient, failed removes partial, rejects invalid period/timeout, resource admission rejects when peak would be exceeded, manifest written with row_count/schema
```

Existing `download_yellow_taxi` tests cover new period, corrected period, resource-admission, and failed-refresh. Live `urbanflow download-yellow-taxi` was not re-run for full 2024-01 (49 MB, 2.9 M rows) in this proof to keep the spike small; the checksum-addressed layout and `unchanged` reuse are exercised by the fixture tests.

## First analytical slice (proof 3)

### Grain and tables

- `bronze.raw_yellow_trips` — source fidelity (19 columns + `ingested_at_utc`, `source_period`, `source_sha256`)
- `silver.clean_trips` — validated rows
- `silver.quarantine_yellow_trips` — rejected rows + `quarantine_reason`
- `gold.zone_hour_demand` — `(city, zone, hour)` where `hour` is pickup hour floored to UTC, measures `trip_count`, `avg_distance`, `avg_fare`, `sum_fare`

### Validation (per contracts.md Quality)

`src/urbanflow/lakehouse/taxi.py:_quarantine_table` checks missing pickup/dropoff, `dropoff < pickup`, `PULocationID`/`DOLocationID` 1..265, `passenger_count` 1..6 when not null, `trip_distance`/`fare_amount` ≥ 0. Quarantined rows keep `quarantine_reason` for replay.

### Gold

`_gold_aggregate` groups validated trips by `city="NYC"`, `zone=PULocationID`, `hour=floor(pickup_at_utc, UTC)`, and source-period provenance via `pyarrow.compute.floor_temporal` and `group_by(...).aggregate`. Naive source timestamps are explicitly interpreted as `America/New_York`; ambiguous/nonexistent DST wall times are rejected.

### Writer

Same PostgreSQL JDBC catalog `spike_pg` as the foundation spike, file warehouse `file://…/.local/spike-iceberg/warehouse` (and S3 variant `s3://warehouse` via `load_spike_s3_catalog` with S3Mock). `publish_yellow_slice` (`src/urbanflow/lakehouse/taxi.py:publish_yellow_slice`) replaces only the selected period in each table, preserves other periods and prior snapshots, and returns a `SliceResult` with row counts, snapshot IDs, and a manifest at `.local/lakehouse/period=YYYY-MM/slice_manifest.json`.

### CLI

```sh
.venv/bin/python -m urbanflow publish-yellow-slice --config configs/local.example.toml --period 2024-01 --limit-rows 1000
.venv/bin/python -m urbanflow publish-yellow-slice --config configs/local.example.toml --period 2024-01 --limit-rows 500 --use-s3
```

### Evidence (via `venv`, Trino 476)

File slice (2000 rows, deterministic first row-group slice of the January 2024 sample):

```text
input_rows=2000 accepted_rows=1967 quarantined_rows=33 gold_rows=79
bronze_snapshot_id=4927899062146843803 silver_snapshot_id=6615126961177340699 gold_snapshot_id=4927899062146843803
# Trino via venv:
# iceberg.bronze.raw_yellow_trips count 2000
# iceberg.silver.clean_trips count 1967
# iceberg.silver.quarantine_yellow_trips count 33
# iceberg.gold.zone_hour_demand count 79
# SELECT city, zone, hour, trip_count FROM iceberg.gold.zone_hour_demand ORDER BY trip_count DESC LIMIT 3
# → (NYC,79,2024-01-01 00:00 UTC,108) etc.
# Invariant: accepted + quarantined == input (1967+33==2000)
```

S3 slice (500 rows, `s3://warehouse` via S3Mock at `localhost:9090`/`s3mock:9090`):

```text
input_rows=500 accepted_rows=493 quarantined_rows=7 gold_rows=61
# Trino via same catalog, fs.native-s3.enabled=true, s3.endpoint=http://s3mock:9090
```

Unit:

```sh
.venv/bin/python -m pytest tests/unit/test_taxi_slice.py -v
# 3 passed: quarantine splits reasons, gold counts, publish via file warehouse with manifest
```

### Reconciliation and pinning

### Period-scoped replacement check (2026-09-27)

The publisher now tags all four tables with `source_period`. A targeted Iceberg test seeds tables using the earlier whole-table schema, publishes a new February period, publishes a corrected January release, and repeats that correction. It verifies that the two periods remain, January contains only the corrected checksum, accepted and rejected counts reconcile, and period labels appear in quarantine and Gold. Legacy quarantine/Gold tables are migrated once by deriving periods from their timestamps (using the existing landing period for null timestamps); ambiguous legacy rows fail safely. The test uses a disposable SQLite catalog and temporary directory. It does not test concurrent writers or atomic commits across the four tables.

- Accepted/quarantined/duplicate totals reconcile per run; parsing failures are separate and block publication via the quarantine table.
- Gold is recomputed from Silver; a correction publishes a new snapshot/version for the affected period while prior snapshots remain available. Each run's manifest lists its `bronze_snapshot_id`/`silver_snapshot_id`/`gold_snapshot_id`.
- One-trip trace: a raw pickup at `2024-01-01T00:10:00, PULocationID 1` appears in `bronze`, passes quarantine into `silver`, and contributes to `gold` hour `2024-01-01T00:00:00Z, zone 1`.

### Resource

Slices are limited via `--limit-rows` to stay within the 20 GB peak (file warehouse <1 MB for 2000 rows; full 2.9 M rows would be ~50 MB Parquet + Iceberg snapshots, still within budget but not required for the proof). Full January 2024 file remains at `.local/source-samples/nyc-tlc/yellow_tripdata_2024-01.parquet` (2,964,624 rows, 49,961,641 bytes, SHA-256 `c4d59…`).

## Follow-on status

- Stage 1 follow-on work (latest-month discovery, duplicate preservation policy, and bounded query demo) was completed on 2026-09-28; see the [roadmap evidence](../roadmap.md).
- dbt-trino Gold ownership transfer and Airflow scheduling with idempotency (Stage 2).
- Measured comparison report under `docs/operations/benchmarks.md` and portal export.
