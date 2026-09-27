# Architecture decisions and unresolved choices

[Documentation index](../README.md)

**Status:** proposed design baseline synthesized from planning notes. These records describe the reconciled design intent; implementation choices marked open still require evidence. They are not measured findings.

## ADR-001 — Kafka as the event backbone

**Context:** producers, replay, and consumers need decoupling and retained events. **Decision:** use Kafka for the planned streaming backbone. **Alternatives:** multiple brokers or direct producer-to-processor coupling. **Trade-off/consequence:** Kafka introduces partitions, retention, and operational work; avoid adding another broker without a distinct requirement.

## ADR-002 — Separate streaming and batch compute

**Context:** low-latency state and large historical transformations have different needs. **Decision:** Flink owns stateful event-time processing; Spark owns distributed batch, backfills, and features. **Alternatives:** one engine for all workloads. **Trade-off/consequence:** two runtimes need shared contracts and reconciliation; Airflow schedules finite jobs rather than continuously routing events.

## ADR-003 — Shared Iceberg lakehouse

**Context:** Spark, Flink, and Trino need a shared analytical model. **Decision:** Iceberg tables over object storage with a shared compatible catalog. The Stage 1 spike selects PyIceberg 0.12.0 + PyArrow 25.0.1 as the temporary writer, a PostgreSQL JDBC catalog (`catalog_name=spike_pg` on the existing `urbanflow` Postgres) as the shared catalog, and Trino 476 (connector `iceberg`, catalog type `jdbc`). Both a file warehouse under `.local/spike-iceberg/warehouse` and an S3 warehouse `s3://warehouse` via S3Mock (`adobe/s3mock:latest`) are proven. REST (Polaris) remains a candidate if credential vending is required. **Alternatives:** engine-specific storage or PostgreSQL as the analytical store. **Trade-off/consequence:** catalog selection, commit compatibility, file maintenance, and snapshot retention become explicit responsibilities; file and S3 warehouses share the same JDBC catalog with different filesystem configs (`fs.native-local` vs `fs.native-s3`).

## ADR-004 — Bronze, Silver, and Gold quality boundaries

**Context:** source fidelity and business-ready data serve different purposes. **Decision:** preserve raw/Source-shaped Bronze, normalize/validate Silver, and publish defined-grain Gold. **Alternatives:** direct raw-to-dashboard transformations. **Trade-off/consequence:** extra storage and processing buy traceability and reprocessing; quarantine and reconciliation must accompany publication.

## ADR-005 — Canonical multi-city contracts

**Context:** city schemas and context coverage differ. **Decision:** share a canonical mobility core while retaining source-specific fields. **Alternatives:** independent city stacks or forcing identical schemas. **Trade-off/consequence:** adapters, namespaces, units, temporal/spatial mappings, and null policies require explicit contracts.

## ADR-006 — Local-first, cloud-portable deployment

**Context:** reproducibility and cost matter before a production cluster is justified. **Decision:** local profiles for the full logical platform, a bounded public demo, and a production cloud reference. **Alternatives:** a permanently running full cloud stack. **Trade-off/consequence:** local tests have scale/HA limits; cloud portability must be tested when implemented.

## ADR-007 — Agent tools are a security boundary

**Context:** natural-language access must not grant unrestricted analytical access. **Decision:** structured authorized tools, SQL validation, read-only credentials, budgets, and evidence-backed answers. **Alternatives:** direct unrestricted generated SQL. **Trade-off/consequence:** guard/evaluation work is mandatory; unsupported requests fail explicitly and the product remains usable without an LLM.

## ADR-008 — Separate current-state serving from history

**Context:** current demand reads and historical scans have different latency and durability needs. **Decision:** introduce Redis with live serving while retaining Iceberg/Trino for analytical history. **Alternatives:** query the lake for every refresh or use cache as history. **Trade-off/consequence:** define cache expiry, ordering, rebuild, and freshness; cache writes and lake writes need reconciliation.

## Reconciling the internal notes

| Tension                                             | Documentation resolution                                                                                                         |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Full technology list versus a small first milestone | Stage 1 implements a bounded historical lakehouse/query slice with explicit latest-release semantics; no full-stack prerequisite |
| Catalog listed as a later addition                  | A shared catalog decision is required for coherent Iceberg access; Polaris is a candidate, not a selected dependency             |
| MLflow described as optional and later as locked    | Plan tracking for Stage 5 with MLflow as the intended tool; no Stage 1 dependency                                                |
| OpenLineage called both essential and later         | Require traceable lineage now in manifests/metadata; defer its automation through OpenLineage/Marquez                            |
| Kafka Connect called high priority and optional     | Add only for a concrete connector need; avoid overlapping Flink sink ownership                                                   |
| Registry, Redis, and Loki absent from initial lock  | Include as target additions at the contract/streaming, live-serving, and operations stages                                       |
| Singular and plural context-topic names             | Use `weather.observations`, `traffic.observations`, and `city.events` consistently in this design                                |
| Different timestamp/location names                  | Propose canonical `*_timestamp` fields with explicit location/zone mappings; finalize in versioned schemas                       |
| Hourly Gold and short-horizon forecasts             | Require finer-grained feature/label definitions for 15/30/60-minute forecasts                                                    |
| Security and idempotency placed in Stage 7          | Establish basic correctness and permission boundaries with each feature; Stage 7 broadens hardening                              |

## Open implementation choices

| Choice                                                                                      | Resolve by                                                                                                                                                              |
| ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Stage 1 writer, catalog implementation, engine/version compatibility                        | Foundation spike 2026-09-26: PyIceberg 0.12.0 + PyArrow 25.0.1, Postgres JDBC `spike_pg`, Trino 476 proven on both file and S3 (`s3://warehouse` via S3Mock) warehouses |
| dbt-trino adapter/materializations and transfer of Gold ownership                           | Stage 2 modelling spike                                                                                                                                                 |
| Historical periods, latest cadence, correction handling, retention and publication manifest | First source contract and refresh implementation                                                                                                                        |
| Canonical physical types, units, timezone/DST, stable identity, corrections                 | First source contract                                                                                                                                                   |
| Registry product, Avro/Protobuf, compatibility mode, retention/partition policy             | Streaming implementation                                                                                                                                                |
| Watermarks, lateness, dedup horizon, sink commit semantics, correction ownership            | Streaming correctness tests                                                                                                                                             |
| Redis keys, TTLs, recovery and stale-read policy                                            | Live serving implementation                                                                                                                                             |
| Feature/label grain, temporal cutoffs, model gates, anomaly thresholds                      | ML experiments                                                                                                                                                          |
| Trace backend, telemetry retention, alert thresholds, resource budgets                      | Operations implementation                                                                                                                                               |
| Authentication system, demo backend, LLM/model provider                                     | Product implementation                                                                                                                                                  |
| RPO/RTO/SLOs, HA, provider/region, concrete cost model                                      | Any production deployment                                                                                                                                               |

Resolve each choice with a focused ADR or versioned contract when evidence is available. Keep optional tools deferred until they solve a demonstrated problem.

## ADR-009 — Transformation ownership and local inspection

**Status:** proposed direction, pending compatibility tests. Spark owns Bronze-to-Silver historical transformations. dbt through Trino is the intended Silver-to-Gold modelling path from Stage 2. Stage 1 may use a minimal selected writer for Gold; migration transfers ownership explicitly. DuckDB provides local file inspection and a controlled benchmark baseline. Test exact adapter, table materialization and write semantics before adopting dbt-trino. Avoid two writers owning the same model.

## ADR-010 — Separate stream tables and maintain the lake

**Status:** design baseline. Flink owns separate `rt.zone_5min` and `rt.anomalies` products. Batch jobs recompute comparable windows independently; reconciliation must specify grain, revision and replay scope. Set snapshot retention from the first table and add compaction/cleanup with tested safety rules. This adds maintenance work but bounds local storage and preserves clear writer ownership.

## ADR-011 — Export-backed public portal

**Status:** initial delivery direction. Publish versioned, validated Gold exports for a small static Next.js portal. Add runtime APIs/database services with features that require them. Keep FastAPI, Redis, forecasting and agent designs for later stages. Defer ClickHouse and OpenMetadata until a measured requirement justifies them.

## ADR-012 — Local resource policy and expandable architecture

**Status:** design baseline incorporating explicit user constraints. Enforce the 20 GB peak working-data ceiling only in the local deployment profile. Keep source adapters, transforms, storage/catalog configuration and serving contracts modular. An expanded deployment can retain more history and use more workers without changing logical data semantics. Compatibility, migration, capacity and recovery tests remain required.

## ADR-013 — Historical and latest data coexist

**Status:** design baseline. Support parameterized historical backfills and scheduled discovery of latest published releases through a shared idempotent pipeline. Version source corrections, coordinate overlapping writers, pin historical experiments, and advance current consumer views only after validated publication. Source lag and pipeline lag are different metrics. Exact cadence, periods, retention and freshness objectives are implementation decisions.

## ADR-014 — Isolate metadata storage behind a repository factory

**Context:** ingestion needs durable run and source-release metadata, and database construction inside workflows would couple acquisition logic to one backend. **Decision:** workflows depend on `MetadataRepository`; a centralized factory returns a cached adapter instance for each connection configuration. Each adapter operation continues to open its own short-lived connection. **Alternatives:** instantiate the PostgreSQL adapter in each workflow or share a process-global database connection. **Trade-off/consequence:** adapter choice stays localized and repository instances are reused, while connection lifecycle and transactions remain owned by the adapter. PostgreSQL is the only implemented backend; adding another requires an explicit factory selection rule and compatible persistence behavior.

## ADR-015 — Stage 1 catalog/writer/Trino compatibility spike

**Context:** The foundation milestone requires a single writer and Trino to coordinate through a shared catalog before publishing the first taxi table. **Decision:** select PyIceberg 0.12.0 + PyArrow 25.0.1 as the Stage 1 writer, a PostgreSQL JDBC catalog (`spike_pg`) as the shared catalog, and Trino 476 with `iceberg.jdbc-catalog`. Both a local file warehouse (`.local/spike-iceberg/warehouse` with `fs.native-local.enabled=true` and dual mounts for Trino's `/tmp` prefix) and an S3 warehouse (`s3://warehouse` via `adobe/s3mock:latest` with `fs.native-s3.enabled=true`) are proven and share the same `spike_pg` catalog. This reuses the existing `urbanflow` Postgres, avoids a separate catalog server, and matches the target Iceberg v2 format. **Alternatives:** SQLite file catalog (proven only for isolated write/read, not shared), REST/Polaris/Nessie (extra operational cost), Spark writer (deferred to Stage 2). **Evidence:** `scripts/spike_iceberg_trino.py` (file) and `scripts/spike_iceberg_s3.py` (S3, `load_spike_s3_catalog` with `s3.endpoint=http://localhost:9090`) each write 2 rows and verify via Trino (`DESCRIBE`/`count(*)`/`SELECT`); see `docs/spikes/2026-09-26-foundation-compatibility.md`.

## ADR-016 — Reproducible ingestion with resource admission

**Context:** Stage 1 requires a bounded, checksum-addressed landing with bounded retries and admit-control before unbounded downloads. **Decision:** keep period-derived TLC URLs, atomic `.incoming` → `os.link` publication, SHA-256-addressed `bronze/raw/.../release=sha256-…`, `unchanged` reuse of verified releases, `refresh` preserving corrections as new SHA, and `working_data_peak_gb` admission via `_working_data_size_bytes` + `Content-Length` (`src/urbanflow/ingestion/sources/nyc_taxi.py:_fetch`). Each release writes a `manifest.json` with SHA, byte_count, row_count/schema (via `pyarrow.parquet`). **Evidence:** `tests/unit/test_ingestion.py` 14 tests via `venv` (`unchanged`, `refresh` new SHA, retry, failed cleanup, peak admission, manifest).

## ADR-017 — First Yellow Taxi analytical slice

**Context:** Stage 1 must show one reconciled Bronze→Silver→Gold path with quarantine and a pinned snapshot before expanding periods or engines. **Decision:** publish `bronze.raw_yellow_trips` (source + provenance), `silver.clean_trips` + `silver.quarantine_yellow_trips` (reasons: missing timestamps, ambiguous/nonexistent New York local timestamps, dropoff_before_pickup after UTC normalization, invalid zone 1..265, passenger_count 1..6, negative distance/fare), and `gold.zone_hour_demand` `(city,zone,hour)` via `src/urbanflow/lakehouse/taxi.py:publish_yellow_slice` using the same `spike_pg` JDBC catalog (file and `s3://warehouse` via `adobe/s3mock`). CLI `urbanflow publish-yellow-slice --limit-rows N` controls slice size for the 20 GB peak. **Evidence:** 2000-row slice of January 2024 (`input 2000 = accepted 1967 + quarantined 33`, `gold 79`) verified via Trino `iceberg.bronze/silver/gold` counts and `DESCRIBE`; manifest at `.local/lakehouse/period=YYYY-MM/slice_manifest.json` pins `bronze/silver/gold_snapshot_id`. Unit `tests/unit/test_taxi_slice.py` (3 tests) and `compose.yaml` (`postgres`+`s3mock`+`trino:476`) via `venv`.

See [source reconciliation](source-reconciliation.md) for all raw-input conflicts, excluded topics and preserved earlier scope. dbt is now a proposed Stage 2 component; Great Expectations is selected on coverage needs. NiFi remains a later ingestion option, not a foundation prerequisite. Both file and S3 file warehouses are proven via the same JDBC catalog; REST (Polaris) remains next for credential vending. Discovery catalogs do not replace the Iceberg catalog.
