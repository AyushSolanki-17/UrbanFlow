# Data model and contracts

[Documentation index](../README.md)

**Status:** proposed logical contracts. A period-based Yellow Taxi downloader and PostgreSQL provenance store are implemented; canonical schemas, table publication, shared-catalog and Trino compatibility remain unimplemented.

## Source plan

| Source                                          | Intended use                                    | Discovery reference                                                                                                                                                                                                                     |
| ----------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NYC TLC Yellow Taxi, HVFHV; Green/FHV as useful | Primary mobility workload                       | [TLC trip records and taxi zones](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)                                                                                                                                         |
| NOAA/NCEI ISD                                   | Relevant weather stations and periods           | [Integrated Surface Database](https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database)                                                                                                                        |
| NYC permitted events                            | Event timing, location, and type                | [Historical events](https://data.cityofnewyork.us/City-Government/NYC-Permitted-Event-Information-Historical/bkfu-528j/data), [current events](https://data.cityofnewyork.us/City-Government/NYC-Permitted-Event-Information/tvpp-9vvx) |
| NYC traffic volume                              | Independent mobility signal                     | [Automated counts](https://data.cityofnewyork.us/Transportation/Automated-Traffic-Volume-Counts/7ym2-wayt), [historical counts](https://data.cityofnewyork.us/Transportation/Traffic-Volume-Counts-Historical-/btm5-ppia)               |
| TLC geography                                   | Zone lookup, polygons, centroids, spatial joins | TLC link above                                                                                                                                                                                                                          |
| Chicago Taxi Trips                              | Second-city portability                         | [Chicago source cited in planning](https://data.cityofchicago.org/Transportation/Taxi-Trips/wrvz-psew)                                                                                                                                  |
| NYC collisions, optional                        | Disruption context                              | [Motor Vehicle Collisions](https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95)                                                                                                                      |

Confirm dataset version, coverage, access, license/attribution requirements, and publication lag before ingestion. Download only relevant weather stations and periods. Do not assume every city supplies every context category.

### Initial Yellow Taxi sample evidence

Use TLC's **January 2024 Yellow Taxi Trip Records** as the fixed compatibility-spike sample. The source period is `2024-01`; TLC does not identify this monthly object with a separate numbered release. TLC says monthly files are typically published with a two-month delay and notes that `cbd_congestion_fee` was added starting with 2025 data. January 2024 therefore provides a stable pre-change schema candidate, not a guarantee that other periods share it. Source: [TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), file [yellow_tripdata_2024-01.parquet](https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet), downloaded 2026-09-26.

The dataset is presented through NYC Open Data. The portal's [Terms of Use](https://data.cityofnewyork.us/stories/s/Terms-of-Use/k9k7-3cje/) and NYC's [open-data legal policy](https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-204577) provide the governing terms; NYC describes public datasets as usable without restrictions, while asking users to identify source and version and describe modifications. TLC does not attach a distinct license identifier to this monthly Parquet file, so do not label it CC0 or another formal license. Retain attribution to NYC TLC, source period/version and any modifications in derived publications. The website terms also disclaim warranties. Recheck terms before redistribution.

Retrieval record: 49,961,641 bytes; SHA-256 `c4d59da7bbc8abaeeeb1727947ee93d9891a71acb42854bd80db1571b2030510`; stored at `.local/source-samples/nyc-tlc/yellow_tripdata_2024-01.parquet` (ignored). The complete file has 2,964,624 rows and 3 Parquet row groups. Its 19 columns are `VendorID`, `tpep_pickup_datetime`, `tpep_dropoff_datetime`, `passenger_count`, `trip_distance`, `RatecodeID`, `store_and_fwd_flag`, `PULocationID`, `DOLocationID`, `payment_type`, `fare_amount`, `extra`, `mta_tax`, `tip_amount`, `tolls_amount`, `improvement_surcharge`, `total_amount`, `congestion_surcharge`, and `Airport_fee`. The two trip-time columns are Parquet `timestamp[us]` without a timezone; sampled values are naive local-looking wall times. Normalize source timezone/DST only under an explicit contract; do not silently interpret these as UTC. Zone fields are integer TLC Taxi Zone IDs (pickup `PULocationID`, dropoff `DOLocationID`), not names or coordinates.

The following definitions follow TLC's [Yellow Taxi Trip Records Data Dictionary](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf). Types are the observed Arrow/Parquet types in this January 2024 file, not selected canonical Silver types. “Nullable” reflects whether any nulls were present in this complete file.

| Source column           | Description                                                                                                 | Observed Parquet type         | Nulls in file |
| ----------------------- | ----------------------------------------------------------------------------------------------------------- | ----------------------------- | ------------: |
| `VendorID`              | Code identifying the TPEP provider that submitted the trip record.                                          | `int32`                       |             0 |
| `tpep_pickup_datetime`  | Date and time the taxi meter was engaged.                                                                   | `timestamp[us]` (no timezone) |             0 |
| `tpep_dropoff_datetime` | Date and time the taxi meter was disengaged.                                                                | `timestamp[us]` (no timezone) |             0 |
| `passenger_count`       | Driver-reported number of passengers.                                                                       | `int64`                       |       140,162 |
| `trip_distance`         | Distance reported by the taximeter, in miles.                                                               | `double`                      |             0 |
| `RatecodeID`            | Final rate code in effect at the end of the trip. TLC documents `99` as null/unknown.                       | `int64`                       |       140,162 |
| `store_and_fwd_flag`    | `Y` if the trip was held in vehicle memory before sending to the vendor due to connectivity; `N` otherwise. | `large_string`                |       140,162 |
| `PULocationID`          | TLC Taxi Zone where the taximeter was engaged (pickup zone ID).                                             | `int32`                       |             0 |
| `DOLocationID`          | TLC Taxi Zone where the taximeter was disengaged (dropoff zone ID).                                         | `int32`                       |             0 |
| `payment_type`          | Code identifying the payment method or outcome, such as credit card, cash, dispute, or voided trip.         | `int64`                       |             0 |
| `fare_amount`           | Time-and-distance fare calculated by the meter, in USD.                                                     | `double`                      |             0 |
| `extra`                 | Miscellaneous extras and surcharges, in USD.                                                                | `double`                      |             0 |
| `mta_tax`               | MTA tax triggered by the metered rate, in USD.                                                              | `double`                      |             0 |
| `tip_amount`            | Tip amount. Automatically populated for credit-card tips; cash tips are not included. USD.                  | `double`                      |             0 |
| `tolls_amount`          | Total tolls paid for the trip, in USD.                                                                      | `double`                      |             0 |
| `improvement_surcharge` | Taxi improvement surcharge assessed on trips, in USD.                                                       | `double`                      |             0 |
| `total_amount`          | Total amount charged to the passenger, excluding cash tips, in USD.                                         | `double`                      |             0 |
| `congestion_surcharge`  | Congestion surcharge collected for the trip, in USD.                                                        | `double`                      |       140,162 |
| `Airport_fee`           | Fee for a pickup at LaGuardia or John F. Kennedy Airport, in USD.                                           | `double`                      |       140,162 |

Full-file null counts were scanned with PyArrow 25.0.1. A 100-row projection round-tripped through a disposable local Iceberg table using PyIceberg 0.12.0 with PyArrow 25.0.1, a SQLite SQL catalog, and local filesystem data storage. This is evidence for local Iceberg write/read only. The temporary catalog is not selected as the shared Stage 1 catalog, and Trino compatibility remains open. The full Parquet file and spike scratch database remain under ignored `.local/` storage; they are not repository fixtures.

The implemented command `uv run --locked urbanflow download-yellow-taxi --config configs/local.toml --period YYYY-MM` uses the direct URL pattern `https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_YYYY-MM.parquet`. A selected monthly file can therefore be downloaded entirely by Python without a browser, SDK or manual file selection. The caller supplies the period; discovery of the newest available month is not implemented. The base path is configured with `data_dir`. Files are placed under `bronze/raw/source=nyc_tlc/service=yellow/period=YYYY-MM/release=sha256-<digest>/yellow_tripdata_YYYY-MM.parquet`. Repeats reuse a verified local release. Use `--refresh` to check again for source corrections; changed bytes are retained under a new checksum path.

The configured PostgreSQL database stores attempt history and immutable source releases. Attempt records include run ID, source ID, period, URL, status, timezone-aware UTC start/completion, retry count, destination, byte count, SHA-256, ETag, HTTP Last-Modified and error detail. Release records include checksum-derived release ID, retrieval time, path, size, checksum, ETag and HTTP Last-Modified. `row_count` and `schema_json` are nullable fields reserved for later validation. HTTP Last-Modified is not assumed to be the source publication timestamp. `MetadataRepository` defines the backend interface, and a central factory reuses a cached adapter instance per connection configuration. The adapter owns short-lived connections; no shared connection is held by the singleton repository.

## Canonical trip model

The source spec alternates between `pickup_time` and `pickup_timestamp`, and between location and zone fields. This documentation proposes the names below; adapters must explicitly map source names. Types and null policies must be formalized before implementation.

| Field                                   | Meaning / contract requirement                                                |
| --------------------------------------- | ----------------------------------------------------------------------------- |
| `trip_id`                               | Stable source ID or documented deterministic identity                         |
| `city`                                  | City namespace, required even if zone IDs look globally unique                |
| `service_type`                          | Controlled source/service category                                            |
| `pickup_timestamp`, `dropoff_timestamp` | Normalize with documented source timezone and DST handling                    |
| `pickup_location`, `dropoff_location`   | City-specific spatial representation, mapped to canonical zones when possible |
| `pickup_zone`, `dropoff_zone`           | Proposed normalized zone references; namespace by city                        |
| `passenger_count`                       | Nullable where absent; valid domain defined per source                        |
| `trip_distance`                         | Normalize units and retain original representation in Bronze                  |
| `fare_amount`                           | Define currency, meaning, and source-specific exceptions                      |

Keep source-specific fields in Bronze or a documented extension, rather than inventing values to make city schemas identical. Geography mappings must be versioned when boundaries change.

A streaming envelope additionally needs `event_id`, source identity, schema version, ingestion time, and replay-run identity. Keep original event time separate from replay arrival time. Identity/fingerprint rules must explain collisions, source corrections, and whether repeated replay runs are isolated or intentionally deduplicated.

## Event contracts

Proposed topic names, normalized to the plural names from the main spec:

| Topic                  | Payload purpose            |
| ---------------------- | -------------------------- |
| `mobility.yellow`      | Yellow Taxi trips          |
| `mobility.hvfhv`       | High-volume for-hire trips |
| `weather.observations` | Weather context            |
| `city.events`          | Permitted-event context    |
| `traffic.observations` | Traffic measurements       |
| `mobility.anomalies`   | Derived anomaly events     |

Each versioned contract should declare owner, schema, event-time field, source cadence, freshness expectation, nullability, ranges, units, compatibility policy, partition key, identity, retention, and quality rules. Store these under proposed `data-contracts/` and `schemas/` directories when implementation begins.

Avro versus Protobuf and the registry implementation remain open. Validate compatibility in CI before producers publish new versions. A proposed mobility partition key is `(city, pickup_zone)`; measure hot-zone skew and define behavior for missing zones. No partition count or retention duration is selected yet.

## Lakehouse layers

| Layer         | Planned tables                                                                                              | Publication rule                                           |
| ------------- | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Bronze        | `raw_yellow_trips`, `raw_hvfhv_trips`, `raw_weather`, `raw_events`, `raw_traffic`                           | Source fidelity and provenance retained                    |
| Silver        | `clean_trips`, `normalized_weather`, `normalized_events`, `normalized_traffic`, `geographic_reference`      | Schema, quality, units, and location normalization applied |
| Gold          | `zone_hour_demand`, `zone_hour_features`, `forecasting_features`, `mobility_anomalies`, `model_predictions` | Business grain, feature versions, and lineage documented   |
| Optional Gold | `travel_time_features`                                                                                      | Created only if travel-time work is included               |

`zone_hour_demand` has a proposed grain of `(city, zone, hour)` (all supported services combined; service breakdowns require explicit columns or a separate service-grain product) and measures such as trip count, average distance/fare, and HVFHV count. Weather, event counts, and traffic require explicit aggregation and join rules before inclusion; joining raw context rows directly can multiply trip counts.

Define canonical window keys as unambiguous UTC instants with `[start, end)` bounds; keep local timezone/offset for display and calendar features. Two repeated local hours during a DST transition must remain distinct. Ambiguous or nonexistent source-local timestamps need a declared resolution/quarantine policy, not an implicit host-timezone conversion.

Hourly tables alone cannot supply all 15/30/60-minute forecasting targets. Define finer-grained feature/label tables during ML design, with a fixed prediction origin and horizon. Avoid treating five-minute streaming windows and hourly Gold rows as interchangeable.

Choose partitions, file sizes, compaction, snapshot retention, and write modes through measurements. Retain snapshots needed for reproducibility before expiring them.

## Quality and semantics

Initial rules cover missing identity/timestamps, dropoff before pickup, invalid locations, unknown city/service, unreasonable passenger count, and negative distance/fare. Source exceptions such as adjustment records need explicit handling rather than silent coercion. Custom code checks and, with SQL modelling, dbt tests gate Silver/Gold publication. Add Great Expectations where it provides required coverage; no framework substitutes for defined quality rules.

Quarantine preserves the original record, source reference, rule/version, reason, and processing run so fixes can be replayed. Track accepted, rejected, and duplicate counts and reconcile them against source manifests. Define mutually exclusive terminal dispositions so their sum equals the parsed input row count; parsing/file failures are tracked separately and block publication according to policy. Preserve source row provenance when equal-valued rows may represent distinct trips; a repeated file or event is not the same thing as two legitimate identical records.

Use event-time windows (five minutes in the initial streaming proposal). Watermark delay, allowed lateness, state retention, too-late routing, correction behavior, and deduplication horizon remain to be chosen. Record per-stage delivery semantics and sink idempotency; checkpoints alone do not prove end-to-end exactly-once results.

Temporal experiments should use older periods for training and later periods for validation/test. The source plan suggests 2024, 2025, and available 2026 data; freeze exact cutoffs and actual availability in the experiment manifest. Context and features must only use information available at the prediction origin.

## Release identity, freshness and ownership

Each source manifest needs a dataset/source ID, source period, discovered release/version (or checksum when no release ID exists), source publication time if available, retrieval time, byte/row counts, schema version, ingestion run ID and immutable landing reference. Track validation/publication status separately from successful download. Never invent a source publication timestamp when it is unavailable.

Distinguish event time, source release time, observed-at time, ingested-at time and curated publication time. Published tables/exports expose coverage, source versions and freshness. A historical experiment pins snapshots and rules; a latest view advances only after validation. See [data lifecycle](../architecture/data-lifecycle.md) for overlap, corrections and retention.

| Product                              | Writer / grain                                                              | Correction boundary                                                           |
| ------------------------------------ | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Bronze source tables                 | Ingestion writer; source release and original record                        | New immutable release plus manifest; preserve provenance                      |
| `clean_trips` and normalized context | Spark after foundation spike                                                | Rebuild/merge affected release partitions under a validated identity policy   |
| `zone_hour_demand` and Gold models   | Stage 1 selected writer, then proposed dbt-trino; `(city, zone, hour)`      | Recompute affected windows; publish a new snapshot/version                    |
| `rt.zone_5min`                       | Flink; `(city, zone, window_start, replay_run_id)` for isolated experiments | Defined revision/late-event policy; no concurrent batch writer                |
| `rt.anomalies`                       | Flink operational candidates                                                | Candidate identity, rule version and window revision; distinct from ML scores |
| Public export                        | Export job over validated snapshots                                         | Whole versioned release, with rollback to a retained valid export             |

The `rt` schema is a logical namespace to validate with the chosen catalog. Hourly demand retains the original canonical name `zone_hour_demand`; `zone_hourly_demand` in the raw review is an alias, not a second table. Proposed daily/revenue/performance marts require grains and acceptance checks before creation. Dead-letter topic names and retention remain part of the streaming contract decision.

## Context geography

Weather retains station identity, observation time, resolution, coverage and a documented station-to-city/zone mapping. An assigned city/station reading is not a direct measurement inside each taxi zone. Handle missing observations and publication availability explicitly.

Census/ACS enrichment is optional. Select geographic vintage, measures and uncertainty treatment, and build a versioned crosswalk between source geography and taxi zones. Aggregation rules depend on the measure: a median cannot generally be aggregated with a simple area-weighted average. Do not infer individual characteristics or causation from area-level associations. Census work must not block the initial lakehouse.
