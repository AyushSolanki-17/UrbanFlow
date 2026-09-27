# Project context for contributors and agents

[Documentation index](README.md)

**Baseline updated: 2026-09-28.** The Python package validates local TOML configuration, downloads monthly NYC Yellow Taxi Parquet objects to checksum-addressed storage with resource-admission and manifests, and publishes a Bronze/Silver/Gold slice (`bronze.raw_yellow_trips`, `silver.clean_trips`/`quarantine_yellow_trips`, `gold.zone_hour_demand`) via PyIceberg 0.12.0 + PyArrow 25.0.1 and a PostgreSQL JDBC catalog `spike_pg`, queryable via Trino 476 over file and S3 (`s3://warehouse` via S3Mock) warehouses. A 2,000-row slice reconciles 1,967 accepted + 33 quarantined and produces 79 Gold rows. Re-publication now replaces only the selected source period, preserves other months and previous Iceberg snapshots, and is covered for new periods and corrections. Stage 1 is complete with TLC latest-period discovery, explicit duplicate and timezone policies, and a bounded read-only Trino query surface. Scheduling, same-period writer coordination and atomic multi-table release advancement remain future work. The repository also has locked development dependencies, Ruff, local pytest, documentation checks, pre-commit hooks and CI; see [contributor setup](../CONTRIBUTING.md) and [agent instructions](../AGENTS.md). Resource settings remain planning budgets, not general admission controls. Read this page before proposing work; then read the relevant contract, architecture page, and roadmap milestone. Documentation describes intended behavior until code and recorded tests demonstrate it.

## What we are building

UrbanFlow is a local-first mobility lakehouse and streaming engineering project, beginning with NYC Yellow Taxi and zone references. It should trace a record from source to a published aggregate, demonstrate correctness and recovery, and explain measured performance. Forecasting, grounded analytics, and a multi-city product remain part of the longer-term design.

The development machine has 16 GB RAM and a 512 GB SSD. Target roughly 10 GB of project data in routine work, with a **20 GB peak working-data ceiling**, including copies, retained snapshots, Kafka logs, checkpoints, scratch, exports, and telemetry. Container images are tracked separately; available disk space still limits all work. The provisional stack RAM budget is 8–10 GB, to be measured. Normal development should require no paid cloud infrastructure. Run services selectively.

## Reference map

Use the task routing in [AGENTS.md](../AGENTS.md) to select relevant pages. This is an onboarding order, not a requirement to read every document for each task.

1. [Overview](overview.md) for goals and scope.
2. [Platform](architecture/platform.md) and the [HTML architecture review](diagrams/architecture.html) for responsibilities and paths.
3. [One-trip walkthrough](architecture/one-trip.md) and [contracts](data-model/contracts.md) for physical representations, identities, and publication rules.
4. [Decisions](decisions/README.md) and [source reconciliation](decisions/source-reconciliation.md) for selected directions, unresolved choices, and excluded ideas.
5. [Roadmap](roadmap.md), [local constraints](architecture/local.md), and [benchmark protocol](operations/benchmarks.md) before implementation or experiments.

## Working rules

- Curated Markdown is the design baseline. The HTML is its visual companion. Neither a raw conversation nor a diagram silently selects a dependency or proves compatibility.
- Preserve useful earlier scope, but separate near-term work from later ML, agent, city, and deployment extensions.
- Start with a small reproducible historical slice. Select the catalog and writer through a compatibility spike before a larger download.
- Spark is the intended Bronze-to-Silver batch owner. dbt through Trino is the proposed Silver-to-Gold owner from Stage 2; adapter/materialization support is an implementation gate. DuckDB provides local inspection and a comparison baseline.
- Flink owns separate streaming tables. Redis is introduced with current-state API serving. ClickHouse, OpenMetadata, and Census enrichment are deferred.
- Publish a static export-backed portal first. Keep cloud topology, provider costs, and software versions unverified until implementation research and tests select them.
- Never describe historical replay as a live NYC feed or a single-host experiment as a production capacity result.
- Update the relevant docs with decisions and evidence in each meaningful implementation commit. Keep internal chats, datasets, secrets, volumes, and large artifacts out of Git.

## What comes next

The Stage 1 foundation spike (file/S3 catalog/writer/Trino), reproducible ingestion with resource admission/manifests, period-aware publication, latest-period discovery, duplicate disposition and the minimal Trino query demo are implemented. Next is Stage 2 compatibility work: validate dbt-trino ownership transfer and produce a measured report. See the [source contract](data-model/contracts.md), [commit sequence](roadmap.md#first-implementation-commits), and spike records in `docs/spikes/2026-09-26-foundation-compatibility.md` and `docs/spikes/2026-09-26-ingestion-and-slice.md`.

Internal files are optional background and remain ignored. Future work must be possible using only this public documentation. For an unresolved conflict, record the rationale and affected contracts rather than relying on whichever source was read last.
