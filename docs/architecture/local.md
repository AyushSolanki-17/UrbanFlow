# Local deployment design

[Documentation index](../README.md) · [Deployment diagram](../diagrams/deployment.drawio)

**Status:** proposed Docker Compose organization. Compose files, images, resource limits, bootstrap scripts, and quick-start commands do not yet exist.

The local machine is the development and failure-testing laboratory. Do not assume it can run every target service at once or represent a highly available cluster. Validate container architecture compatibility and measure CPU, memory, disk, and thermal limits on the actual host.

## Proposed profiles

| Profile       | Services/workloads                                                                                                                           | Purpose                                        |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Foundation    | MinIO, selected Iceberg catalog, Trino, selected ingestion/table writer; metadata DB if needed                                               | First Bronze → Silver → Gold query path        |
| Streaming     | Shared storage/catalog plus Kafka, registry, Flink and replay producer; query engine only for verification, Redis with current-state serving | Event-time processing and recovery             |
| Batch         | Storage/catalog plus Spark; dbt and Trino for Gold modelling, Airflow with scheduling                                                        | Transformations, backfills, feature generation |
| Product       | Next.js and validated exports first; FastAPI/query/cache services, inference and agent when needed                                           | Dashboard and API development                  |
| Observability | Prometheus, Grafana, OpenTelemetry Collector; Loki and trace backend as introduced                                                           | Instrumentation and diagnosis                  |
| ML            | Feature access, training runtime, MLflow, artifact storage, inference                                                                        | Reproducible experiments and serving           |

These are logical groupings, not committed profile names. Shared dependencies should be reused rather than duplicated. NiFi is introduced with source-flow needs; do not make every ingestion experiment depend on the full target stack.

## Developer workflow to implement

1. Select a small, fixed source period and validate source terms and schema.
2. Start the storage/catalog/query dependencies with explicit health checks.
3. Fetch data and write a reproducible manifest; load Bronze, validate Silver, build Gold.
4. Run a known Trino query and compare totals to accepted/quarantined/duplicate input counts.
5. Add the necessary profile for batch, streaming, or product work.
6. Save configuration, dataset identity, and measurements before tearing down an experiment.

Persist object data, catalog metadata, and any recovery-critical state outside ephemeral containers. Document reset and backup procedures before providing destructive convenience scripts. Use configuration templates and uncommitted secrets; bind administrative interfaces locally by default.

The local topology can demonstrate restart and recovery behavior, but a single host cannot demonstrate survival of a host or availability-zone failure. Separate those claims in reports.

## Resource envelope, not architecture limit

The current host has 16 GB RAM and a 512 GB SSD. Aim for roughly 10 GB working data in routine use and **at most 20 GB peak working data**. Allocate a provisional 8–10 GB RAM to the active stack and aim to retain 100+ GB free SSD space; verify available capacity before running. These are planning constraints, not measured service reservations. Profiles can share storage and lightweight telemetry; do not assume the full stack fits simultaneously.

Count raw downloads, managed Parquet files, snapshot-retained files, Kafka logs, checkpoints, metadata, exports, telemetry, scratch, and temporary rewrites in the working-data total. Parquet inside an Iceberg table is the same physical data, not a second storage allocation. Independent raw and curated copies do count separately. Track container images/build caches separately and include them in host free-space checks. Reserve compaction/download headroom before admitting new work.

Use small input samples initially and measure their storage amplification before expanding. Local historical periods and a recent rolling window coexist under a configurable retention policy. Before a refresh, estimate new bytes plus peak rewrite needs; if it cannot fit, pause admission or safely retire eligible data. Do not delete experiment-pinned snapshots or silently evict needed history to satisfy the latest refresh.

These limits belong in local configuration. Remote object storage, expanded retention, larger workers and more partitions are later deployment options using the same logical contracts. They require capacity and compatibility tests, not a redesign of the data product.

DuckDB can inspect a frozen sample without starting distributed services. Spark/dbt are jobs rather than permanent residents where possible. Governance services remain deferred. Start only required dependencies for an experiment and record its actual resource peak.
