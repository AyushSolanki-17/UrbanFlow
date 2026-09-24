# Benchmark and learning protocol

[Documentation index](../README.md) · [Reliability](reliability.md)

**Status:** experiment design; no measurements exist. Every component should have a stated problem, physical operation, measurement, failure mode and recovery demonstration.

## Repeatable runs

Freeze input manifest/checksums, accepted-row rules, query semantics, table snapshots, feature/model versions when relevant, software versions, code commit and configuration. Record host/OS/container architecture, CPU allocation, total memory cap, engine settings, file layout, background load and peak disk usage.

Run one query engine at a time under comparable total CPU/memory limits, including workers and required services. Record startup separately from query execution. For a warm-cache comparison, discard one explicit warm-up and report the median and range of at least five measured runs. Retain all run results and failures. Cold-cache runs are a separate series with a documented cache-reset procedure; restarting a process alone does not prove the OS page cache was cleared. Do not present p95 from five runs as a reliable tail estimate.

Compare identical data and SQL semantics, reconcile results, and disclose differences in supported operations, data access, materialization and connector behavior. If DuckDB reads a frozen Parquet export while Trino reads Iceberg, label that distinction and report export preparation separately. Do not describe it as an identical table-access benchmark.

## Bounded experiments

| Experiment | Compare / measure | Correctness guard |
| --- | --- | --- |
| CSV versus Parquet | Same sampled records; bytes, projection/filter read time | Same rows, types, null and timestamp interpretation; preserve original TLC Parquet |
| File sizes and compaction | Small-file fixture versus compacted copy; count, scanned bytes, latency, rewrite cost | Same snapshot contents; retain rollback snapshot only within budget |
| Partitioning | Same queries on alternative layouts; pruning and scan volume | Equal filtered aggregates |
| Spark joins/skew | Broadcast versus shuffle, skewed fixture, repartition/salting; shuffle, task duration, memory | Equal join multiplicity and results |
| DuckDB / Trino / Spark | Fixed query suite and controlled resources; startup, runtime, bytes read | Equal results; document access-mode differences |
| Kafka/Flink replay | Increase rate gradually; lag, checkpoint duration, backpressure, late records | Reconcile durable results after stop/restart |
| Quality and recovery | Inject bad rows, duplicate/restart, incompatible schema | Expected quarantine/rejection and final counts |

Use small generated edge-case fixtures for skew and pathological file layouts; record that they are synthetic. The review's 100,000 tiny files and 40% hot-zone examples are experiment ideas, not observed facts or mandatory local workloads. Stop before disk/RAM limits are exceeded. Reuse historical inputs across experiments and release scratch copies safely afterward.

## Report artifact

Each future report should contain question, setup, command/configuration, input and output identities, expected result, raw measurements, summary statistics, correctness comparison, resource peaks, failure/recovery observations and limitations. Include a source-to-output trace where relevant. Store small reports and result tables in Git; store large logs/data externally with reproducible references. Publish only completed results on the portal.

These measurements characterize this machine and configuration. A small cloud portability run tests deployment assumptions, not production scale or high availability. Keep resource constraints and measured improvements separate from marketing examples in the raw notes.
