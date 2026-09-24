# Public portal and published data

[Documentation index](../README.md) · [Cloud tiers](cloud.md)

**Status:** planned Next.js/TypeScript consumer. The HTML architecture document is available now; no portal, export job, public hosting or API is deployed.

## First release

Begin with architecture, engineering, and data pages. Architecture explains the design and current build status. Engineering publishes completed benchmark/recovery reports with methodology and limitations. Data describes sources, coverage, freshness, geography and quality exclusions. Empty evidence sections say that experiments are pending.

Later add an explorer, mobility map, demand/revenue views, lineage and labelled streaming replay. Preserve the original forecast, anomaly, Ask UrbanFlow and system-health ambitions for their corresponding roadmap stages. Route names are proposals, not existing URLs. Avoid committing to all pages at once.

## Export contract

Validated Gold snapshot → export job → versioned release → static portal.

An export records `export_id`, schema version, source table/snapshot IDs, transformation/code version, city and time coverage, generation time, units/timezone, quality status, record count, payload checksums and replay status where applicable. These are proposed fields to formalize with the exporter. Split payloads by page or time range, set a measured browser payload budget, and aggregate away unnecessary trip-level detail.

Validate every payload before publication. Publish a complete release under a new version, then switch its manifest/pointer so readers never mix releases. Retain a previous valid release for rollback within the disk budget. Display coverage and generated-at time; a publicly reachable page does not imply continuously arriving data. Export failure keeps the previous release visible with its original freshness metadata.

JSON is the initial browser format. Parquet may be an optional download or backend artifact; browser-side Parquet support is a separate implementation choice. Export size is measured, not an obligation to upload the review's illustrative 100–500 MB range.

## When runtime services are justified

Introduce FastAPI for authenticated tools, forecasts, replay controls, or queries that cannot be served from bounded exports. Use Trino for historical lakehouse queries and Redis for current state as described in the platform design. A small public database may hold curated subsets if interactive filtering needs it; it does not replace the engineering lakehouse. Consider ClickHouse only after measured data volume, query latency or concurrency warrants another service.

Hosting/storage/provider choices and costs remain open. Local engineering can remain offline between runs while a published export remains available. No free-tier or always-free hosting assumption is required by the design.
