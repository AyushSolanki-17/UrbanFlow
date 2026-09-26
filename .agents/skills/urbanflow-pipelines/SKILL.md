---
name: urbanflow-pipelines
description: Implement or review UrbanFlow source adapters, ingestion, lakehouse publication and streaming replay. Use when data identity, historical/latest refresh, corrections or recovery behavior changes.
---

# UrbanFlow pipelines

Read `docs/data-model/contracts.md` and `docs/architecture/data-lifecycle.md`, plus the relevant milestone in `docs/roadmap.md`. Consult `docs/architecture/platform.md` for writer ownership and `docs/architecture/local.md` for the local execution budget. Repository layout in `docs/project-guide.html` is a proposal; create only the modules required by the current feature.

## Data invariants

- Write Python docstrings in Google style. Use comments sparingly to explain intent, constraints, or non-obvious decisions; write them as complete sentences and do not restate the code.

- Parameterize source/city, period, release and run identity. Separate source-specific discovery/mapping from reusable ingestion and publication logic.
- Distinguish event time, source publication time, ingestion time and curated publication time. Record coverage gaps; absent data is not zero demand.
- Preserve immutable source-release provenance and checksums. Checksums identify content, not revision order. Do not deduplicate legitimate equal-valued rows solely by content.
- Make unchanged input a safe no-op. Corrected periods replace or merge under the declared identity policy; they are not additive copies. Reconcile accepted, rejected and duplicate dispositions.
- Coordinate overlapping backfill/refresh writers. Publish validated snapshot manifests and conditionally advance the current release. A slower old job must not overwrite a newer source revision or remove unaffected periods.
- Protect pinned historical experiments and active recovery state. Estimate peak download/rewrite/checkpoint storage before admitting local work; pause rather than silently delete required history.
- Keep Flink's `rt` products separate from batch-owned tables. Declare replay scope, event identity, watermarks, lateness and dedup horizon. Checkpoint recovery alone does not prove atomic Iceberg/Redis effects.
- Gate replay/ML features by their as-of availability. Future dropoff, duration or final fare cannot become pickup-time inputs. Label replay and delayed-source forecasts honestly.

## Evidence proportional to the feature

Use the test-scope rule in `AGENTS.md` and maintained tools from `CONTRIBUTING.md`. Choose small deterministic cases for the invariants touched by the change: repeat input, source correction, failed publication, or stale competing jobs. Add streaming cases for duplicates, late events, or restart reconciliation only when those behaviors are implemented or changed. Do not build fixtures or suites for planned pipeline stages.

Select/pin catalog, writer and connector versions through a small compatibility test before broad scaffolding or full downloads. Do not require Kafka/Flink to ingest a historical Parquet file. Benchmark only with the methodology in `docs/operations/benchmarks.md`; record dataset and software identities, resource peaks and result correctness.

Update affected contracts and operational instructions with the implementation. Report proven behavior and unresolved semantics separately. Stop at the requested milestone; do not deploy extra infrastructure just because it appears in the target architecture.
