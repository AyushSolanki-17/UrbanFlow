# Platform architecture

[Documentation index](../README.md) · [Editable platform diagram](../diagrams/platform.drawio)

**Status:** target design. The full platform is delivered progressively; it is not the Stage 1 deployment.

## Component responsibilities

| Layer             | Target components                                            | Responsibility                                                                              |
| ----------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| Ingestion         | Python source adapters; NiFi when justified                  | Download, route, normalize source envelopes, retain provenance                              |
| Event contracts   | Versioned schemas, schema registry                           | Validate producer/consumer contracts and compatibility                                      |
| Event backbone    | Apache Kafka                                                 | Retained, partitioned events and independent consumer groups                                |
| Streaming         | Apache Flink                                                 | Event-time aggregation, late events, state, checkpoints, anomaly candidates                 |
| Batch             | Apache Spark / Spark SQL                                     | Bronze-to-Silver cleaning, joins, feature groundwork, backfills, and distributed benchmarks |
| Lakehouse         | Apache Iceberg, Parquet, shared catalog                      | Bronze/Silver/Gold tables, table metadata, snapshots, evolution                             |
| Object storage    | MinIO locally; cloud object storage later                    | Raw landing files, warehouse data, and durable artifacts                                    |
| Interactive query | Trino; DuckDB for local inspection/comparison                | Bounded analytical queries; controlled single-node baseline                                 |
| SQL modelling     | Proposed dbt-trino from Stage 2                              | Silver-to-Gold models, tests and generated SQL lineage; adapter validation required         |
| Orchestration     | Apache Airflow                                               | Scheduled ingestion, validation, batch jobs, training, evaluation                           |
| Quality           | Code/business rules; dbt tests; Great Expectations if needed | Validation gates and quarantine decisions                                                   |
| Serving           | Redis, FastAPI, Next.js/TypeScript                           | Current state, APIs, and user interface                                                     |
| ML                | Baselines, XGBoost/LightGBM, optional PyTorch model, MLflow  | Forecasts, anomalies, experiment and model traceability                                     |
| Metadata          | PostgreSQL                                                   | Airflow and application metadata; other service metadata if selected                        |
| Operations        | Prometheus, Grafana, OpenTelemetry, proposed Loki            | Metrics, dashboards, instrumentation, and centralized logs                                  |

Iceberg is a table format, MinIO stores objects, and the catalog coordinates table metadata. These are separate responsibilities. Engines access both the catalog and object storage; a catalog is not a proxy through which all data bytes flow. The catalog implementation and shared-engine compatibility must be settled for the foundation milestone.

## Historical and batch path

1. Download source files with period, source identity, and checksums recorded in an ingestion manifest.
2. Preserve raw files in object storage and load source-shaped Bronze tables through a selected writer.
3. Validate and normalize into Silver; quarantine invalid records with reasons and source references.
4. Produce Gold aggregates and features. Spark is the intended Bronze-to-Silver owner; proposed dbt-trino owns Silver-to-Gold from Stage 2 after adapter validation. Stage 1 uses one selected temporary Gold writer and migrates ownership explicitly.
5. Query published tables through Trino. The first portal consumes versioned Gold exports; later APIs expose bounded results to the dashboard and authorized tools.

The Stage 1 writer remains an implementation decision. Kafka and Flink are not required merely to load historical Parquet. NiFi becomes useful as ingestion and routing grow.

## Streaming and current-state path

Historical Parquet → replay producer → Kafka → Flink → Iceberg and Redis.

NiFi/source adapters can also publish source events to Kafka. Registry lookups and compatibility checks support producers and consumers; the registry is not an event transport hop. The initial streaming design assigns durable writes to Flink. Kafka Connect is optional if a separate archival sink proves necessary; it must not accidentally introduce a second writer with conflicting ownership.

Flink uses event time, configurable watermarks, and a documented late-event policy. It publishes windowed aggregates and anomaly candidates durably, and updates Redis for current-state reads. Redis is a serving cache, not the analytical source of truth. Define expiry, correction ordering, rebuild, and stale-data behavior before exposing live demand.

Streaming writes separate `rt.zone_5min` and `rt.anomalies` tables; batch jobs own curated historical tables. Streaming five-minute demand and batch hourly aggregates are distinct products. Specify keys, ownership, revision handling, and reconciliation before using both in a shared dashboard. Backfills must not double-count or overwrite newer streaming results without an explicit policy.

## Query and product paths

- Initial public portal: validated Gold snapshots → versioned JSON export → static Next.js pages.
- Historical analytics with runtime queries: Iceberg → Trino → FastAPI → dashboard.
- Current demand: Flink → Redis → FastAPI → dashboard.
- ML: Gold features → training/evaluation → versioned model → inference API.
- Natural-language analytics: authorized agent tools → validated results → grounded explanation.

Arrows here describe data/result movement. API requests run in the opposite direction when fetching results. The [ML and serving diagram](../diagrams/ml-and-serving.drawio) separates request and training flows.

## Control and operational boundaries

Airflow schedules finite jobs; Kafka and Flink run continuously. PostgreSQL stores operational metadata, not bulk analytical facts. Quality checks gate curated publication. OpenTelemetry instruments services and exports telemetry; a trace storage backend is still to be selected. Grafana displays data from telemetry backends rather than acting as storage.

OpenLineage/Marquez can automate lineage later. Until then, manifests, job IDs, snapshots, feature versions, and model metadata must make lineage inspectable.

## Scope discipline

Contracts, a schema registry, Redis, and Loki are proposed target additions from the tools discussion. They are introduced with the relevant stage, not all on day one. MLflow is planned for the ML stage. Kafka Connect, Debezium, Feast, Kubernetes, Helm, Terraform, Snowflake, and Databricks require a concrete need before adoption. See [decisions and open questions](../decisions/README.md).

## Modularity and expansion

The logical architecture must support a larger deployment independently of the local profile. Local byte/RAM budgets constrain experiments and retention on this host; they do not become hard-coded API, table, city or topology limits.

| Boundary            | Stable interface                                                            | Expansion mechanism                                                                          |
| ------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Sources             | Discovery/manifest, source version, canonical adapter, quality result       | Add adapters/cities without embedding source-specific rules in serving code                  |
| Storage and catalog | Logical table names, snapshot semantics, object-store/catalog configuration | Move endpoints and identities; validate connectors, migrate metadata/data and test restore   |
| Processing          | Versioned contracts, explicit table owners, partition/window semantics      | Increase worker/partition counts through configuration and measured rebalance/recovery tests |
| Orchestration       | Parameterized source, period, release and run identity                      | Schedule latest refresh and bounded historical backfills independently                       |
| Serving             | Versioned API/export schemas, freshness/coverage metadata                   | Static exports, query APIs or a curated database behind the same product semantics           |
| ML and agent        | Feature/model versions and authorized tool contracts                        | Add runtimes/providers without bypassing evaluation, permissions or evidence                 |
| Operations          | Common run/request IDs, metrics and resource policies                       | Environment-specific retention, budgets, scaling and recovery objectives                     |

Start as a small repository with clear modules and configuration; modularity does not require a microservice for every function. Avoid shared mutable files, fixed local paths, embedded endpoints or implicit global single-city assumptions. Separate deployment configuration from business transformations. Source discovery and period selection belong outside transform logic.

Historical backfills and latest-source refreshes share the ingestion and publication contract in [data lifecycle](data-lifecycle.md). Their run identities and scheduling differ. Continuous Kafka/Flink consumers remain separate from finite Airflow jobs. Scale-out and cloud portability require compatibility and recovery evidence; a configurable endpoint alone is insufficient.
