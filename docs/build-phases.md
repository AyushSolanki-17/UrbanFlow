# UrbanFlow, phase by phase

[Documentation index](README.md) · [Visual project guide](project-guide.html) · [Canonical roadmap](roadmap.md)

This guide explains the build in plain engineering terms: what each phase produces, which tools have a role, and why they are introduced. It is an orientation guide; the contracts, architecture pages, and roadmap define implementation details and acceptance evidence.

## The project in one line

Take published city trip records, preserve where they came from, clean and summarize them, check the results, and make the summaries queryable and visible. Add reliable refresh, streaming experiments, forecasts, and an analytics assistant after that core works.

The first analytical journey is:

```text
NYC taxi source → local landing and manifest → validated tables → demand by zone and hour → query → chart
```

## What exists now

The repository has documentation, quality tooling, and a Python package that validates local configuration. A January 2024 NYC Yellow Taxi file has also been downloaded into ignored local storage and inspected. A 100-row projection was written to and read from a temporary local Iceberg table with PyIceberg and PyArrow. That proves a local experiment can work; it does not establish the shared catalog and writer choice, Trino compatibility, or a repeatable ingestion pipeline. See the [source sample evidence](data-model/contracts.md#initial-yellow-taxi-sample-evidence) and [roadmap status](roadmap.md).

## Build phases and technology roles

| Phase                                       | What we make                                                                                                       | Tools and why                                                                                                                                                                                                                                                             |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Understand and land a source sample      | Choose a fixed source period, keep a local copy, and record its identity, URL, checksum, size, and retrieval time. | **Python** for source bookkeeping and repeatable download code. **Parquet** is the source file format. The January 2024 sample is already present locally, but a reusable source adapter and manifest workflow still need implementation.                                 |
| 2. Prove table storage and querying         | Write a tiny table, read it back, and settle compatible table-writer, catalog, and query choices.                  | **Iceberg** tracks table contents and snapshots; the **catalog** coordinates table metadata; object storage holds file bytes. **PyIceberg + PyArrow** were used in the local spike. **Trino** compatibility remains to be checked. The catalog/writer pair is still open. |
| 3. Validate and normalize trips             | Turn source-shaped rows into consistent records; reject or quarantine bad rows with a reason.                      | Use **Python** for small deterministic checks. **Spark** is the intended owner for larger Bronze-to-Silver batch transformations. It can process larger datasets in parallel; it is not needed to inspect the first sample.                                               |
| 4. Publish a useful aggregate               | Build demand counts at a declared grain, initially city + zone + hour, and reconcile totals.                       | Use the selected writer for the initial Gold table. **dbt through Trino** is the proposed Stage 2 SQL-modeling path, pending adapter and write-semantics checks. **DuckDB** can inspect small local samples and provide a comparison baseline.                            |
| 5. Query and show the result                | Ask a known question and display the answer with coverage and source-version context.                              | **Trino** is the planned analytical query service. A **static Next.js portal** can read versioned data exports first, so the UI does not require an always-running backend.                                                                                               |
| 6. Refresh safely and schedule work         | Discover new or corrected releases, rerun without double-counting, and preserve pinned historical experiments.     | **Python adapters** handle source discovery and manifests. **Airflow** is planned to schedule finite refreshes and backfills. It is introduced when repeatable jobs need scheduling, not for the first manual sample.                                                     |
| 7. Test streaming and recovery              | Replay records as events; exercise duplicates, late arrivals, restarts, and slow consumers.                        | **Kafka** retains and distributes events; **Flink** handles event-time windows and stateful processing. These create a separate streaming product and arrive after the historical tables work. Historical replay is a simulation, not a live taxi feed.                   |
| 8. Add other sources and cities             | Bring in weather, events, traffic, other taxi services, then test portability with Chicago.                        | Add **Python source adapters** and versioned contracts. Shared canonical fields allow comparison while source-specific details remain preserved. Each source needs explicit coverage, units, time, and missing-data rules.                                                |
| 9. Add forecasts and anomalies              | Predict demand, compare with simple baselines, and track model results.                                            | Start with standard statistical/ML baselines; select model libraries based on measured need. **MLflow** is planned for experiment and model tracking. Training must use fixed data snapshots and temporal cutoffs to avoid future-data leakage.                           |
| 10. Add grounded natural-language questions | Let users ask supported questions and receive answers tied to query results.                                       | An assistant calls **authorized tools** that query Trino or approved forecast/anomaly results. Tool permissions, SQL checks, budgets, and evaluations keep it bounded. The data product remains usable without an assistant.                                              |

**Shared engineering tools:** Git tracks code and small fixtures; pytest checks Python behavior; Ruff formats and lints Python; npm scripts check Markdown, HTML, and repository formatting. These are already configured. Large raw datasets, local table volumes, credentials, and generated artifacts stay out of Git.

## The sensible first implementation slice

The sample data and local Iceberg write/read experiment are useful preparation. The repeatable pipeline has not been built yet. A small next slice is:

1. Confirm the sample and source contract, including the source timezone, source fields, and attribution.
2. Choose a candidate table writer and catalog, then prove the same tiny table can be read through the intended query path, including Trino.
3. Implement a repeatable local ingestion run with a manifest rather than relying on a one-off download.
4. Validate a small set of rows and produce one known zone/hour aggregate.
5. Rerun it and verify counts, duplicates, and source identity are explained.

Only after this slice is repeatable should the project expand the input period or bring in Spark, schedulers, streaming services, portal backends, or ML infrastructure. Follow the [roadmap](roadmap.md) for exit evidence and the [contracts](data-model/contracts.md) for data semantics.

## Terms to keep straight

- **Bronze, Silver, Gold** are quality and purpose layers: source-shaped, cleaned/normalized, and product-ready.
- **Parquet** is a file format. **Iceberg** is a table format that tracks files and snapshots. The **catalog** coordinates table metadata. They do different jobs.
- **Historical backfill** processes chosen past periods. **Latest refresh** discovers newer published releases. **Replay** re-sends historical records to test streaming behavior.
- A tool shown here as **planned** is not necessarily installed, selected, compatible, or measured. The [decisions page](decisions/README.md) tracks open choices; the [platform page](architecture/platform.md) gives the detailed boundaries.
