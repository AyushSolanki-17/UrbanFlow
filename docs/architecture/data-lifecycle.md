# Historical data and latest-source refresh

[Documentation index](../README.md) · [Contracts](../data-model/contracts.md)

**Status:** required design behavior; discovery, scheduling, manifests and publication jobs remain to be implemented.

## Implemented source-acquisition slice

The CLI fetches an explicitly requested monthly TLC Yellow Taxi object using the period-derived CloudFront URL. Python's standard library handles HTTP and streaming. Files are written to a temporary path, checked against `Content-Length` and Parquet magic bytes, hashed with SHA-256, then placed under a source/period/checksum path without replacing an existing release. Repeating a request reuses a verified local release; `--refresh` fetches the source again so changed content is retained separately. Failed attempts are recorded and partial files are removed. This does not discover the latest period or publish a table.

Each attempt and immutable release is recorded in the configured PostgreSQL metadata database. Run metadata includes source ID, period, URL, status, timezone-aware UTC start/completion, attempts, output path, byte count, SHA-256, ETag, source Last-Modified header and failure detail. Release records reserve nullable row count and JSON schema metadata for later validation. HTTP Last-Modified is distinct from source publication time; it is not treated as a verified publication timestamp. See the [source contract](../data-model/contracts.md) for the CLI and path layout.

## Two workloads, shared semantics

Historical backfills select fixed source periods/releases for reproducible analysis and ML. Latest refresh discovers newly available releases and corrections on a source-specific cadence. Both use the same adapter, manifest, validation, identity and publication code, with explicit run parameters. “Latest” is the newest validated source release, which may describe events from weeks or months earlier. Historical replay is a third workload, using frozen inputs and its own run identity; it is not a substitute for refreshing published data.

Do not hard-code one month or year into transformations. Configure city/source, start/end periods, release policy, ingestion cadence, retention and resource budget. Track coverage by source and period so missing periods do not masquerade as zero demand. API/portal responses distinguish event coverage, source publication time when known, last successful ingestion and last successful publication.

## Ingestion and publication state

1. Discover candidate source objects and compare their identity/version/checksum with the manifest. Unchanged successful releases are no-ops; failed releases can resume safely.
2. Admit the run only if its estimated download, transform and rewrite peaks fit the active environment's budget. Schedule refreshes and backfills separately so a large backfill cannot silently starve recent data.
3. Download to an isolated location, verify integrity, and preserve an immutable landing reference. Record source identity and observed timestamps.
4. Validate schema and normalize to Bronze/Silver with accepted, quarantined and duplicate counts. New or incompatible schemas fail publication or take an explicit migration path.
5. Recompute affected Gold periods and dependent context joins. Reconcile totals before exposing them.
6. Commit table snapshots and publish a release manifest referencing the exact snapshots used. Multiple table commits are not assumed to be one transaction; readers needing a consistent multi-table view use that manifest.
7. Advance the consumer-visible release pointer through serialized publication or a compare-and-swap against its expected predecessor. Completion time is not release precedence: a slow older backfill must not replace a newer source revision or remove already published periods. Rebase/revalidate a stale candidate against the current release, preserving unaffected source-period mappings. Explicit rollback is a separate audited operation.
8. Mark the run published only after its consumer-visible release succeeds. A failed refresh leaves the previous valid release available with unchanged freshness labels and an observable failure status.

## Overlap, corrections and backfills

A source correction creates a new source release, not a second additive copy of trips. Track release precedence per source and period; if the source provides no ordered revision identifier, define how discovery of changed bytes is confirmed and record the supersession explicitly. A checksum identifies content but does not order revisions. Choose stable identity, replacement/merge rules and affected-period scope with the first contract. When stable source row IDs are absent, a content fingerprint alone may not distinguish a corrected row from a new trip: replacing the validated source period may be safer. Record the selected rule and test it.

Serialize or otherwise coordinate competing writes to the same source/period/table. A retry or overlapping historical/latest run must not double count. Retain superseded release provenance and any pinned experiment snapshot according to policy. Recompute dependent Gold/export products and identify which published release supersedes which. If pinned history prevents a local refresh from fitting, report the conflict and pause or move the workload; never silently break reproducibility.

Streaming tables have separate ownership and replay scope. Batch can independently recompute the same windows for reconciliation but does not write Flink-owned tables. A consumer chooses a declared authoritative product/cutover rule; it must not sum overlapping batch and streaming results.

## Retention and expansion

Local development retains a bounded historical selection plus a recent window. Choose actual periods only after measuring input sizes, storage amplification and the historical baseline needed by analyses/models. Older data can remain reproducibly downloadable, but a source URL is not a guarantee that an exact historical release will remain available. Preserve checksums and required artifacts, or label a run no longer reproducible if its dependencies are removed.

An expanded deployment can retain all selected history in durable object storage and run parallel backfills with configurable concurrency, partitioning and resource controls. Contracts and consumer schemas stay stable. Retention, source cadence, freshness objectives, snapshot pin duration and refresh/backfill fairness remain per-environment decisions to document before production use.

## Acceptance cases

Verify: repeat the same release; discover a new period; ingest a corrected period; overlap a refresh with a backfill that finishes last; fail halfway through multi-table publication; encounter an incompatible schema; miss a source release; and run out of disk headroom. Each case must produce an explainable current release, accurate coverage/freshness and reconciled counts. Freeze one historical experiment, run a latest refresh, and demonstrate that the frozen result remains reproducible while the current view advances.
