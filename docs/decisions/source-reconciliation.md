# Planning-source reconciliation

[Documentation index](../README.md) · [Decision register](README.md)

**Reviewed 2026-09-24.** This records how the earlier design and newly supplied context were reconciled. The source files remain unchanged under ignored `docs/internal/`; they are not required by public readers.

## Source roles

| Internal input                               | Useful contribution                                                                                                        | Treatment                                                                                                |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `UrbanFlow_Architecture_and_Project_Spec.md` | Mobility product, canonical model, ML/agent, eight-stage delivery                                                          | Preserve long-term scope and correctness requirements                                                    |
| `chats/tools_context.md`, `tech_stack.md`    | Technology roles, contracts, catalog, Redis, operations, learning inventory                                                | Distinguish a learning inventory from installed dependencies                                             |
| `chats/deployment_context.md`                | Local, public-demo, production-reference tiers                                                                             | Preserve portable boundaries and bounded cloud work                                                      |
| `gpt_context.md`                             | Explicit 16 GB RAM / 512 GB SSD host and 10–20 GB preference; one-row learning method; measured experiments; public portal | Adopt constraints and engineering method; filter exploratory alternatives and promotional examples       |
| `architecture-review.html`                   | Supplied visual design, ownership gaps, maintenance, benchmark fairness, portal scope                                      | Adapt as the primary public HTML; retain its layout and interactions while correcting conflicting claims |

## Resolutions

| Conflict or review finding                                    | Current disposition                                                                                                                     | Where / when            |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| Older 40M+ and accelerated-replay targets versus local limits | Keep as historical workload ideas, subordinate to measured bytes and resource ceilings; no minimum-volume requirement                   | Overview, local design  |
| Review proposes five phases and omits ML/agent                | Keep eight canonical stages; include modelling/orchestration in Stage 2 and deliver a small portal incrementally                        | Roadmap                 |
| NiFi versus Python/dlt ingestion                              | Python adapter first; NiFi only when flow management earns its cost; dlt remains an alternative                                         | Platform, Stage 1       |
| Spark and dbt overlap                                         | Spark owns Bronze → Silver; proposed dbt-trino owns Silver → Gold from Stage 2; one temporary Stage 1 Gold writer                       | ADR-009                 |
| DuckDB newly called core                                      | Adopt as lightweight local inspection/comparison, with tested access to selected files or snapshots                                     | Platform, benchmarks    |
| Catalog called optional or conflated with discovery           | Shared Iceberg catalog is foundational; REST is a candidate interface, not a chosen product. OpenMetadata is optional discovery/lineage | ADR-003, Stage 1 spike  |
| Catalog and dbt adapter described as universally compatible   | Require pinned engine/catalog/adapter tests; no compatibility guarantee inferred from a diagram                                         | Stage 1 / Stage 2 gates |
| Streaming and batch mutate the same table                     | Separate `rt` tables, declared owners, revisions and reconciliation                                                                     | ADR-010, contracts      |
| Maintenance absent from early pipeline                        | Bound retention from first write; add tested maintenance before sustained streaming                                                     | Reliability             |
| Great Expectations mandatory versus dbt tests first           | Validation gates are mandatory; use code checks initially, dbt tests with SQL models, add Great Expectations if coverage requires it    | Platform, contracts     |
| Registry, Redis, MLflow disappear in newer diagram            | Preserve their earlier stage-specific roles; HTML links to broader platform and ML design                                               | Platform, ML design     |
| OpenMetadata versus OpenLineage/Marquez                       | Defer service deployments; retain source/job/snapshot lineage now and dbt manifests when available                                      | Reliability             |
| Static portal versus always-on FastAPI/database               | Export-backed portal first; API/database only for features needing runtime queries                                                      | Portal, cloud           |
| ClickHouse described as supporting/core                       | Deferred pending query latency/concurrency evidence; distinct from Redis current-state cache                                            | Portal                  |
| Weather implicitly measured per taxi zone                     | Preserve observation geography and a documented station/city mapping; no invented zone-level precision                                  | Contracts               |
| Census demographic joins treated as trivial                   | Optional spatial study; versioned geography crosswalk and valid aggregation required, no causal demand claims                           | Contracts               |
| Different topic/table names in HTML                           | Use existing `mobility.*` topics and `zone_hour_demand`; document new `rt` tables                                                       | Contracts, HTML         |
| Raw per-component disk estimates exceed 20 GB together        | Count unique physical bytes and peak rewrite/scratch headroom; component estimates are not simultaneous allocations                     | Local design            |
| Review says no tests/CI exist in plan                         | Earlier docs already require them; carry requirements forward, implementation still absent                                              | Reliability             |

## Deferred and unrelated material

Common Crawl, e-commerce, finance, healthcare, logistics, music, satellite data, and general dataset comparisons are exploratory alternative projects, not UrbanFlow milestones. Hadoop/HDFS/MapReduce/YARN and the wider legacy ecosystem are historical learning context, not runtime dependencies. Resume bullets, LinkedIn drafts, speculative speedups, free-tier claims, and suggested cost figures are not measured project evidence.

Keep Chicago, additional TLC services, weather/events/traffic, ML, agent tools, reliability experiments, and the production reference as staged UrbanFlow scope. Census, collisions, travel time, third-city work, warehouse comparisons, CDC, dedicated feature stores, Kubernetes, and additional orchestration/governance systems require a specific bounded reason before promotion.

The older System Atlas and draw.io files remain available as broader reference views. The supplied review now drives the main HTML presentation; curated docs govern implementation order and choices.
