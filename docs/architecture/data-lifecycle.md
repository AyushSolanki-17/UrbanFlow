# Historical data and latest-source refresh

[Documentation index](../README.md) · [Contracts](../data-model/contracts.md)

**Status:** required design behavior; discovery, scheduling, manifests and publication jobs remain to be implemented.

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
7. Mark the run published only after its consumer-visible release succeeds. A failed refresh leaves the previous valid release available with unchanged freshness labels and an observable failure status.

## Overlap, corrections and backfills

A source correction creates a new source release, not a second additive copy of trips. Choose stable identity, replacement/merge rules and affected-period scope with the first contract. When stable source row IDs are absent, a content fingerprint alone may not distinguish a corrected row from a new trip: replacing the validated source period may be safer. Record the selected rule and test it.

Serialize or otherwise coordinate competing writes to the same source/period/table. A retry or overlapping historical/latest run must not double count. Retain superseded release provenance and any pinned experiment snapshot according to policy. Recompute dependent Gold/export products and identify which published release supersedes which. If pinned history prevents a local refresh from fitting, report the conflict and pause or move the workload; never silently break reproducibility.

Streaming tables have separate ownership and replay scope. Batch can independently recompute the same windows for reconciliation but does not write Flink-owned tables. A consumer chooses a declared authoritative product/cutover rule; it must not sum overlapping batch and streaming results.

## Retention and expansion

Local development retains a bounded historical selection plus a recent window. Choose actual periods only after measuring input sizes, storage amplification and the historical baseline needed by analyses/models. Older data can remain reproducibly downloadable, but a source URL is not a guarantee that an exact historical release will remain available. Preserve checksums and required artifacts, or label a run no longer reproducible if its dependencies are removed.

An expanded deployment can retain all selected history in durable object storage and run parallel backfills with configurable concurrency, partitioning and resource controls. Contracts and consumer schemas stay stable. Retention, source cadence, freshness objectives, snapshot pin duration and refresh/backfill fairness remain per-environment decisions to document before production use.

## Acceptance cases

Verify: repeat the same release; discover a new period; ingest a corrected period; overlap a refresh with a backfill; fail halfway through multi-table publication; encounter an incompatible schema; miss a source release; and run out of disk headroom. Each case must produce an explainable current release, accurate coverage/freshness and reconciled counts. Freeze one historical experiment, run a latest refresh, and demonstrate that the frozen result remains reproducible while the current view advances.
