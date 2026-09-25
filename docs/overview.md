# Project overview

[Documentation index](README.md)

UrbanFlow aims to turn real public mobility records into an inspectable data product. The core is data engineering and distributed systems; forecasting and a secure analytics agent build on that foundation.

## Product questions

- What is demand by zone, and how does it change over time?
- What demand is expected in 15, 30, and 60 minutes?
- Which zones have unusual demand, and what contextual evidence accompanies it?
- How do weather, events, traffic, and service types relate to mobility?
- Can the same platform support another city without discarding source-specific information?
- Can replay and recovery experiments demonstrate correctness under duplicates, late events, and failures?

Weather and events can provide evidence associated with an anomaly; their presence alone does not establish causation.

## Scope

Start with NYC Yellow Taxi, zone reference data, and a manageable historical period. Add HVFHV and contextual sources as the pipeline matures. Chicago is the second-city portability test. Select a third city only after comparing coverage, quality, volume, and canonical-model compatibility. Motor vehicle collisions and travel-time estimation are optional extensions.

The intended dashboard includes Overview, Live Demand, Map, Forecast, Anomalies, Historical Analytics, Ask UrbanFlow, and System Health. Live simulation must identify historical replay explicitly and display measured service telemetry.

## Workload tiers

These are earlier planning targets, not downloaded dataset sizes or benchmark results. They remain useful workload categories, but record-count tiers do not override the local byte budget. Use 100–500 MB inputs for development and 2–5 GB inputs for normal experiments where measured expansion fits; reserve larger experiments for a total peak working-data footprint of at most 20 GB locally. Larger deployments can use larger datasets without changing the logical contracts.

| Tier                     | Target workload                           | Purpose                                               |
| ------------------------ | ----------------------------------------- | ----------------------------------------------------- |
| 0: demo                  | About 100K–500K records                   | Small product demonstration                           |
| 1: development           | About 3M records                          | Rapid local iteration; exact period depends on source |
| 2: integration           | About 10M records                         | Multi-period pipeline validation                      |
| 3: production simulation | About 40M+ records                        | Larger Spark, Trino, and Iceberg experiments          |
| 4: multi-stream          | Yellow Taxi, selected HVFHV, and context  | Heterogeneous sources and features                    |
| 5: stress                | Historical replay at 1x, 10x, 100x, 1000x | Throughput, backpressure, and recovery                |

CI uses smaller deterministic fixtures, not the full demo tier. Synthetic events are reserved for controlled edge cases or stress beyond available real data.

## Principles and boundaries

Use open-source components and local development first. Every component must have a distinct responsibility. Keep the data product usable without an LLM. Treat schemas, quality, lineage, recovery, and reproducibility as pipeline requirements. Publish measured results with configurations rather than asserting production scale.

The intended development model avoids recurring cloud infrastructure spend; local hardware, electricity, optional model APIs, and any temporary cloud workloads still have costs. Kubernetes, cloud warehouses, a dedicated feature store, and CDC are not initial prerequisites.

Public Git content should include code, schemas, small redistributable fixtures, configuration templates, and experiment reports. Large raw datasets, credentials, generated volumes, and large model binaries belong outside Git. Reproducible download scripts are a future deliverable.

## Historical coverage and latest data

Support both reproducible historical analysis and ongoing ingestion of the latest published source data. “Latest” means the newest source release successfully ingested and validated, not a live trip feed. Publication lag, available coverage and ingestion lag must be visible independently. Freeze historical snapshots for experiments while scheduled refreshes advance current analytical products.

Local storage keeps selected historical periods plus a rolling recent window. Exact periods and retention are selected from measured sizes and analytical needs; do not silently drop history needed for training, comparisons or reproducibility. A larger deployment can retain full history using the same contracts. See [data lifecycle](architecture/data-lifecycle.md).

The resource-constrained local setup is one deployment profile, not a limit on the system architecture. Components communicate through versioned contracts and configurable storage/catalog/service boundaries so additional sources, cities, workers and serving backends can be introduced deliberately. See [expansion boundaries](architecture/platform.md#modularity-and-expansion).
