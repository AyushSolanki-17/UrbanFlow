# Reliability, testing, and operations

[Documentation index](../README.md)

**Status:** operational requirements and experiment plans. No incidents, benchmark results, dashboards, alerts, or executable runbooks exist yet.

## Processing guarantees

Document delivery semantics for every producer, processor, and sink. Stable identity, bounded deduplication state, idempotent writes, and recovery reconciliation are required where duplicates would change published totals. Flink checkpointing is one mechanism; it is not proof of exactly-once effects across Iceberg, Redis, and every downstream consumer.

Measure backpressure by slowing a sink and observing Kafka lag, throughput, event-time latency, checkpoint duration, and recovery. Retention and replay windows must be compatible with the worst outage the system is designed to recover from.

## Observability

| Signal | Planned collection / display | Examples |
| --- | --- | --- |
| Metrics | Prometheus and Grafana | Kafka lag, records processed, Flink latency/checkpoints, late/duplicate events, Iceberg write latency, Trino latency, API/model/tool latency |
| Logs | Structured JSON; Loki proposed | Source/run identity, service, operation, request/trace ID, status, error class |
| Traces | OpenTelemetry instrumentation and Collector | API → agent → SQL guard → Trino → response; backend still undecided |
| Data health | Pipeline checks and dashboards | Freshness, quarantine rate, reconciliation counts, missing partitions |
| ML health | Evaluation and serving metrics | Feature/prediction/error drift, model version, prediction age |

Define units and whether latency uses event time or wall-clock time. Proposed metric names in the spec are illustrative, not an implemented exporter contract. Set thresholds from measurements. Redact secrets and sensitive request content; keep metric labels bounded.

## Failure lab

| Experiment | Expected behavior to verify |
| --- | --- |
| Duplicate Kafka event | Published counts follow the documented identity/dedup policy |
| Late / too-late event | Correct event-time window or explicit late-data route/correction |
| Flink worker failure / checkpoint recovery | State restores; reconciled output reveals losses or duplicates |
| Schema evolution | Compatible additions work; incompatible changes are rejected or migrated deliberately |
| Bad records | Quarantine with reasons; curated publication remains valid |
| Spark task failure | Retry/backfill does not publish partial or duplicate output |
| Trino outage / slow query | Bounded failures and timeouts without a cascading outage |
| Model drift | Detection and investigation with versioned evidence |
| Agent SQL / prompt injection | Permissions and resource limits remain enforced |
| API timeout | Bounded retries and explicit failure response |
| Slow downstream sink | Observable backpressure and recovery without silent loss |

Every report should record scenario, setup, data identity, software/configuration, injected fault, expected behavior, observed behavior, recovery steps, metrics, and lessons. A passing recovery test includes output reconciliation, not just a green service status.

## Runbook outlines

Expand these into service-specific executable procedures once deployments and metrics exist.

| Symptom | Inspect / likely causes | Recovery and verification |
| --- | --- | --- |
| Kafka lag grows | Arrival rate, partition skew, consumer errors, Flink pressure, sink latency | Relieve the verified bottleneck or pause replay; confirm lag declines and reconcile counts |
| Flink restarts | Latest successful checkpoint, logs, state-store access, resource pressure | Restore using tested checkpoint/savepoint policy; verify offsets, state, durable outputs, and cache freshness |
| Quarantine spikes | Failing rules, source schema/version, manifests | Fix contract or adapter with fixtures, reprocess isolated records, compare accepted/rejected totals |
| Schema changes | Producer/consumer compatibility and table evolution plan | Gate rollout, migrate or roll back deliberately, replay compatibility tests |
| Trino queries slow | Plans, scan size, partitions/files, concurrency, dependencies | Bound costly work, tune proven bottleneck, compare latency and correctness on the same query set |
| Model quality degrades | Feature freshness, drift, labels, training/serving consistency | Investigate, evaluate challenger or roll back; verify horizon/zone error and freshness |
| Agent fails | Authorization, guard decisions, tool traces, dependencies | Repair failing boundary or disable affected tool; rerun fixed security and grounding cases |

## Tests and delivery gates

Unit tests cover adapters, identities, contract validation, feature logic, anomaly calculations, SQL guard, and tool arguments. Integration tests cover Kafka–Flink, engine–Iceberg/catalog, Airflow–batch, API–query/cache, and agent–tools. End-to-end tests trace a deterministic fixture through curated data and a visible result.

GitHub Actions is the planned CI system: lint, unit/contract checks, data-quality smoke tests, integration/API/tool tests, image build, and security scans. Use small deterministic fixtures. Trivy, dependency updates, and secret scanning are proposed; SBOM tooling can follow when useful. Later deployment gates should include staging smoke tests and a tested rollback path.

## Benchmark protocol

Record dataset and source period, record counts, compressed/uncompressed sizes, hardware, RAM/CPU, software versions, configuration, partitioning, parallelism, run count, and cache state. Measure throughput, p50/p95 latency, memory, runtime, shuffle, scan volume, failures, and recovery duration as relevant.

Compare Spark partitioning, skew, broadcast joins, predicate/column pruning, AQE, and file sizing using repeatable workloads. Measure Iceberg compaction/snapshot behavior and Trino concurrency/scan volume. Keep ML accuracy, inference latency, agent quality, and infrastructure throughput as separate results. Publish limitations; local single-host tests do not establish distributed production capacity.

## Table maintenance and data refresh

Define snapshot retention and experiment pins with the first managed table. Introduce tested compaction before sustained streaming, and schedule it through Airflow when orchestration exists. Record files before/after, bytes rewritten/reclaimed, runtime, peak disk usage and resulting snapshots. Configure maintenance operations for the selected engine/catalog versions rather than assuming procedure names are portable.

Snapshot expiry and orphan cleanup require retention windows that protect active writers, readers, recovery and pinned experiments. Use inventory/dry-run evidence where supported, verify references and age thresholds, and rehearse restore before enabling deletion. Never remove raw/warehouse objects solely because they are absent from the latest snapshot. Keep temporary rewrite headroom under the local cap.

Monitor per-source discovered release, last successful ingestion/publication, event-time coverage, missing periods, source corrections, refresh/backfill queue age and remaining disk headroom. Exercise the [historical/latest acceptance cases](../architecture/data-lifecycle.md#acceptance-cases). A healthy scheduler with stale data is still a data-service failure.

The detailed [benchmark protocol](benchmarks.md) defines cache, resource, engine-comparison and reporting controls. dbt tests complement unit and integration tests; they do not test downloader retries, producer restart state or Flink recovery by themselves.
