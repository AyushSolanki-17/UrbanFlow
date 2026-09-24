# Delivery roadmap

[Documentation index](README.md)

**Status:** all stages below are planned. Completion requires working artifacts and evidence, not documentation alone.

| Stage | Deliverable | Exit evidence |
| --- | --- | --- |
| 1. Data foundation | NYC Yellow Taxi historical slice plus latest-release discovery design, explicit contract, raw landing, Iceberg Bronze/Silver/Gold, quality checks, Trino, minimal query/dashboard demo and local configuration | Fresh checkout can reproduce data loading and a known aggregate; accepted/rejected/duplicate totals reconcile; source and snapshot identities recorded |
| 2. Distributed processing | Spark Bronze-to-Silver transformations, proposed dbt-trino Gold models/tests, DuckDB comparison, Airflow scheduling/backfills | Repeatable correctness checks and runtime/shuffle/partitioning benchmarks on declared hardware and data |
| 3. Streaming | Historical replay, Kafka, registry, Flink event-time windows, checkpoints, anomaly candidates; Redis when current serving starts | Duplicate, late-event, recovery, and slow-sink experiments with reconciled durable outputs and measured telemetry |
| 4. Multi-source / multi-city | Weather, events, traffic, additional services, Chicago adapters | Versioned contracts, explicit missing-context handling, valid temporal/spatial joins, and cross-city comparison |
| 5. ML | Demand forecasts, anomaly models, temporal validation, MLflow, inference, drift monitoring | Baseline comparisons, fixed cutoffs/snapshots, versioned artifacts, inference checks and rollback procedure; travel time remains optional |
| 6. Agent | Trino/forecast/anomaly/context tools, authorization, SQL guard, grounded responses | Fixed evaluation suite covering correctness, grounding, invalid requests, injection, and resource limits |
| 7. Production hardening | Expanded observability, security, CI/CD, load/failure tests, idempotency verification, operational runbooks | Measured recovery and load behavior, bounded failures, tested operational procedures and scans |
| 8. Public platform | Bounded live product, public docs, diagrams, demo data, benchmark and failure reports | Reproducible user journey, honest data/refresh/scale labels, links to measured evidence |

The first stage should be independently demonstrable. It does not require NiFi, Kafka, Flink, Spark, Airflow, ML, and the agent all to be installed first. Choose the minimum viable table writer and shared catalog before building the foundation.

Correctness, authentication where exposed, secret handling, and basic instrumentation accompany each stage. Stage 7 consolidates and deepens those controls rather than introducing them for the first time.

Kubernetes, Terraform, Helm, automated lineage services, CDC, a feature store, enterprise integrations, a third city, and collision data remain extensions. Promote an extension only with a clear problem, a bounded experiment, and an explicit maintenance/cost trade-off.

## First implementation commits

These are commit-sized outcomes, not completed work or prescribed commit hashes. Each should carry its directly affected documentation and meaningful validation.

1. **Foundation compatibility and source contract:** choose exact catalog/writer/engine versions; write/read a tiny Iceberg fixture through the chosen writer and Trino; document DuckDB access mode. Specify identities, correction rules, timestamps and historical/latest release selection.
2. **Reproducible ingestion:** add source discovery, checksummed manifests, bounded download/retry and small fixtures. Demonstrate unchanged release, new period, corrected period and resource-admission behavior.
3. **First analytical slice:** Bronze/Silver/Gold, quarantine, one-trip trace, reconciled aggregate and frozen snapshot. Publish coverage/freshness; prove a refresh advances the current release without changing a pinned experiment.
4. **Modelling and scheduling:** validate dbt-trino, transfer Gold ownership, introduce parameterized Airflow refresh/backfill jobs and safe maintenance. Prove retry/overlap idempotency.
5. **First measured report and portal export:** run a bounded comparison under the benchmark protocol; validate a versioned export and create architecture/engineering/data portal pages.

Continue with streaming and the remaining stages once their dependencies are demonstrated. A small portal may ship before the final public-platform stage; Stage 8 integrates the completed capabilities. ML and agent work remain later scope. Local limits constrain execution plans, not the expandable architecture or support for both historical and latest published data.
