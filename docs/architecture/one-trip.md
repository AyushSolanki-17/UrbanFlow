# One trip from source to published result

[Documentation index](../README.md) · [Interactive architecture](../diagrams/architecture.html)

**Status:** walkthrough to implement, not an execution trace. Consider a hypothetical Yellow Taxi record picked up in zone 161 at 18:31:42 local source time and dropped off in zone 237. Any ID assigned below is a project identity; do not assume TLC provides a unique trip ID.

| Boundary | Physical representation and action | Evidence to retain |
| --- | --- | --- |
| Source → landing | Download an existing monthly Parquet file; store immutable source bytes in MinIO | Source URI, period, checksum, byte/row counts, retrieval time |
| Landing → Bronze | A selected writer creates or safely imports source-shaped Iceberg data files; a committed snapshot makes them table data | Ingestion run, source reference, table and snapshot IDs, writer version |
| Bronze → Silver | Spark reads needed columns, validates timestamps/zones/units, assigns stable identity and writes normalized rows; invalid rows retain quarantine evidence | Input/output snapshots, code/rule versions, accepted/rejected/duplicate counts |
| Silver → Gold | Stage 1 selected writer, then proposed dbt-trino SQL, counts accepted pickups at `(city, zone, hour)` | Model version, dependencies, grain, reconciliation and quality results |
| Gold → query | Trino resolves table metadata through the catalog and reads selected objects | Query ID, snapshot, filters, result and scan measurements |
| Gold → export → portal | Export validated aggregates and metadata into a versioned bounded release; browser reads published JSON | Export ID, source snapshots, time coverage, generation time, checksums |

MinIO is storage; Parquet is the file representation; Iceberg adds table metadata and snapshots; the catalog locates/co-ordinates table metadata. These are not four successive network services. A Parquet file outside a committed table is not automatically an Iceberg row. Preserve source files separately from managed table files unless a tested import/ownership policy permits safe sharing.

In Gold the individual record contributes to a count rather than remaining a displayed trip. A useful trace follows source identity through transformations and demonstrates its contribution using a deterministic fixture; aggregated rows do not imply a full per-trip lineage index. A dbt manifest covers SQL model dependencies, not automatically all ingestion and Spark lineage.

## The same record as an event

1. Read the historical file in a reproducible order and retain original event time. Emit a versioned envelope with `event_id`, `city`, source and replay-run identity.
2. Publish to `mobility.yellow` with the selected partition key. Record acknowledgement and restart position; a producer restart may resend records.
3. Declare whether replay models pickup events or completed-trip publication. Gate fields by that simulated availability; future trip outcomes cannot become pickup-time features. Flink validates, deduplicates within the documented horizon, assigns event-time windows, and routes too-late/invalid events according to the contract.
4. Commit aggregates to `rt.zone_5min` and candidates to `rt.anomalies`. Retain checkpoint, input offsets, table snapshot and revision evidence.
5. Once implemented, update Redis with versioned current state for FastAPI. Iceberg and Redis are separate sink effects; recovery must rebuild/reconcile cache state.
6. Compare a batch recomputation on the same accepted inputs, event-time bounds, and replay scope. Do not add streaming counts to historical counts for the same window.

The acceptance demonstration injects one duplicate, one late record, one invalid record and a restart. It must explain the final count and quarantined/late outputs, not simply show healthy services. Wall-clock replay speed and original event time remain separate throughout.
