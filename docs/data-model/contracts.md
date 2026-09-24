# Data model and contracts

[Documentation index](../README.md)

**Status:** proposed logical contracts. Schemas, SQL DDL, topic configuration, and compatibility tests are not implemented yet.

## Source plan

| Source | Intended use | Discovery reference |
| --- | --- | --- |
| NYC TLC Yellow Taxi, HVFHV; Green/FHV as useful | Primary mobility workload | [TLC trip records and taxi zones](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) |
| NOAA/NCEI ISD | Relevant weather stations and periods | [Integrated Surface Database](https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database) |
| NYC permitted events | Event timing, location, and type | [Historical events](https://data.cityofnewyork.us/City-Government/NYC-Permitted-Event-Information-Historical/bkfu-528j/data), [current events](https://data.cityofnewyork.us/City-Government/NYC-Permitted-Event-Information/tvpp-9vvx) |
| NYC traffic volume | Independent mobility signal | [Automated counts](https://data.cityofnewyork.us/Transportation/Automated-Traffic-Volume-Counts/7ym2-wayt), [historical counts](https://data.cityofnewyork.us/Transportation/Traffic-Volume-Counts-Historical-/btm5-ppia) |
| TLC geography | Zone lookup, polygons, centroids, spatial joins | TLC link above |
| Chicago Taxi Trips | Second-city portability | [Chicago source cited in planning](https://data.cityofchicago.org/Transportation/Taxi-Trips/wrvz-psew) |
| NYC collisions, optional | Disruption context | [Motor Vehicle Collisions](https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95) |

Confirm dataset version, coverage, access, license/attribution requirements, and publication lag before ingestion. Download only relevant weather stations and periods. Do not assume every city supplies every context category.

## Canonical trip model

The source spec alternates between `pickup_time` and `pickup_timestamp`, and between location and zone fields. This documentation proposes the names below; adapters must explicitly map source names. Types and null policies must be formalized before implementation.

| Field | Meaning / contract requirement |
| --- | --- |
| `trip_id` | Stable source ID or documented deterministic identity |
| `city` | City namespace, required even if zone IDs look globally unique |
| `service_type` | Controlled source/service category |
| `pickup_timestamp`, `dropoff_timestamp` | Normalize with documented source timezone and DST handling |
| `pickup_location`, `dropoff_location` | City-specific spatial representation, mapped to canonical zones when possible |
| `pickup_zone`, `dropoff_zone` | Proposed normalized zone references; namespace by city |
| `passenger_count` | Nullable where absent; valid domain defined per source |
| `trip_distance` | Normalize units and retain original representation in Bronze |
| `fare_amount` | Define currency, meaning, and source-specific exceptions |

Keep source-specific fields in Bronze or a documented extension, rather than inventing values to make city schemas identical. Geography mappings must be versioned when boundaries change.

A streaming envelope additionally needs `event_id`, source identity, schema version, ingestion time, and replay-run identity. Keep original event time separate from replay arrival time. Identity/fingerprint rules must explain collisions, source corrections, and whether repeated replay runs are isolated or intentionally deduplicated.

## Event contracts

Proposed topic names, normalized to the plural names from the main spec:

| Topic | Payload purpose |
| --- | --- |
| `mobility.yellow` | Yellow Taxi trips |
| `mobility.hvfhv` | High-volume for-hire trips |
| `weather.observations` | Weather context |
| `city.events` | Permitted-event context |
| `traffic.observations` | Traffic measurements |
| `mobility.anomalies` | Derived anomaly events |

Each versioned contract should declare owner, schema, event-time field, source cadence, freshness expectation, nullability, ranges, units, compatibility policy, partition key, identity, retention, and quality rules. Store these under proposed `data-contracts/` and `schemas/` directories when implementation begins.

Avro versus Protobuf and the registry implementation remain open. Validate compatibility in CI before producers publish new versions. A proposed mobility partition key is `(city, pickup_zone)`; measure hot-zone skew and define behavior for missing zones. No partition count or retention duration is selected yet.

## Lakehouse layers

| Layer | Planned tables | Publication rule |
| --- | --- | --- |
| Bronze | `raw_yellow_trips`, `raw_hvfhv_trips`, `raw_weather`, `raw_events`, `raw_traffic` | Source fidelity and provenance retained |
| Silver | `clean_trips`, `normalized_weather`, `normalized_events`, `normalized_traffic`, `geographic_reference` | Schema, quality, units, and location normalization applied |
| Gold | `zone_hour_demand`, `zone_hour_features`, `forecasting_features`, `mobility_anomalies`, `model_predictions` | Business grain, feature versions, and lineage documented |
| Optional Gold | `travel_time_features` | Created only if travel-time work is included |

`zone_hour_demand` has a proposed grain of `(city, zone, hour)` and measures such as trip count, average distance/fare, and HVFHV count. Weather, event counts, and traffic require explicit aggregation and join rules before inclusion; joining raw context rows directly can multiply trip counts.

Hourly tables alone cannot supply all 15/30/60-minute forecasting targets. Define finer-grained feature/label tables during ML design, with a fixed prediction origin and horizon. Avoid treating five-minute streaming windows and hourly Gold rows as interchangeable.

Choose partitions, file sizes, compaction, snapshot retention, and write modes through measurements. Retain snapshots needed for reproducibility before expiring them.

## Quality and semantics

Initial rules cover missing identity/timestamps, dropoff before pickup, invalid locations, unknown city/service, unreasonable passenger count, and negative distance/fare. Source exceptions such as adjustment records need explicit handling rather than silent coercion. Custom code checks and, with SQL modelling, dbt tests gate Silver/Gold publication. Add Great Expectations where it provides required coverage; no framework substitutes for defined quality rules.

Quarantine preserves the original record, source reference, rule/version, reason, and processing run so fixes can be replayed. Track accepted, rejected, and duplicate counts and reconcile them against source manifests.

Use event-time windows (five minutes in the initial streaming proposal). Watermark delay, allowed lateness, state retention, too-late routing, correction behavior, and deduplication horizon remain to be chosen. Record per-stage delivery semantics and sink idempotency; checkpoints alone do not prove end-to-end exactly-once results.

Temporal experiments should use older periods for training and later periods for validation/test. The source plan suggests 2024, 2025, and available 2026 data; freeze exact cutoffs and actual availability in the experiment manifest. Context and features must only use information available at the prediction origin.

## Release identity, freshness and ownership

Each source manifest needs a dataset/source ID, source period, discovered release/version (or checksum when no release ID exists), source publication time if available, retrieval time, byte/row counts, schema version, ingestion run ID and immutable landing reference. Track validation/publication status separately from successful download. Never invent a source publication timestamp when it is unavailable.

Distinguish event time, source release time, observed-at time, ingested-at time and curated publication time. Published tables/exports expose coverage, source versions and freshness. A historical experiment pins snapshots and rules; a latest view advances only after validation. See [data lifecycle](../architecture/data-lifecycle.md) for overlap, corrections and retention.

| Product | Writer / grain | Correction boundary |
| --- | --- | --- |
| Bronze source tables | Ingestion writer; source release and original record | New immutable release plus manifest; preserve provenance |
| `clean_trips` and normalized context | Spark after foundation spike | Rebuild/merge affected release partitions under a validated identity policy |
| `zone_hour_demand` and Gold models | Stage 1 selected writer, then proposed dbt-trino; `(city, zone, hour)` | Recompute affected windows; publish a new snapshot/version |
| `rt.zone_5min` | Flink; `(city, zone, window_start, replay_run_id)` for isolated experiments | Defined revision/late-event policy; no concurrent batch writer |
| `rt.anomalies` | Flink operational candidates | Candidate identity, rule version and window revision; distinct from ML scores |
| Public export | Export job over validated snapshots | Whole versioned release, with rollback to a retained valid export |

The `rt` schema is a logical namespace to validate with the chosen catalog. Hourly demand retains the original canonical name `zone_hour_demand`; `zone_hourly_demand` in the raw review is an alias, not a second table. Proposed daily/revenue/performance marts require grains and acceptance checks before creation. Dead-letter topic names and retention remain part of the streaming contract decision.

## Context geography

Weather retains station identity, observation time, resolution, coverage and a documented station-to-city/zone mapping. An assigned city/station reading is not a direct measurement inside each taxi zone. Handle missing observations and publication availability explicitly.

Census/ACS enrichment is optional. Select geographic vintage, measures and uncertainty treatment, and build a versioned crosswalk between source geography and taxi zones. Aggregation rules depend on the measure: a median cannot generally be aggregated with a simple area-weighted average. Do not infer individual characteristics or causation from area-level associations. Census work must not block the initial lakehouse.
