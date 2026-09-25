# Cloud deployment design

[Documentation index](../README.md) · [Deployment diagram](../diagrams/deployment.drawio)

**Status:** conceptual deployment reference derived from internal planning, not provisioned infrastructure or a validated provider bill of materials. Verify current service offerings, versions, connectors, regional availability, and pricing before choosing a provider.

## Three deployment tiers

| Tier                 | Scope                                                                                                                  | Intended operating model                                          |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Developer            | Full logical platform through selective local profiles                                                                 | Local development, integration, failure experiments               |
| Public demo          | Static Next.js with curated exports first; FastAPI, inference/agent and database/cache only with features needing them | Small bounded product deployment                                  |
| Production reference | Durable event backbone, distributed compute, shared lakehouse, product and observability services                      | Documented architecture; temporary deployment only when justified |

A public demo must label its data coverage, refresh time, and replay behavior. A small analytical backend may serve curated data through the same API interfaces. PostgreSQL in that tier must not be represented as the full Iceberg analytical lake.

## Portable boundaries

Keep event/data contracts, table semantics, API payloads, feature definitions, and evaluation methods consistent. Endpoints, identity, secrets, networking, object-store configuration, scaling, backup, and telemetry configuration change between environments. Portability requires connector and recovery testing; changing an endpoint is not sufficient evidence.

## Illustrative AWS mapping from the planning notes

These are candidates for later evaluation, not deployment instructions or confirmed compatibility claims.

| Logical component     | Local reference              | AWS candidate                                                                  |
| --------------------- | ---------------------------- | ------------------------------------------------------------------------------ |
| Event backbone        | Kafka                        | MSK                                                                            |
| Object storage        | MinIO                        | S3                                                                             |
| Streaming             | Flink                        | Managed Service for Apache Flink, or self-managed cluster                      |
| Batch                 | Spark                        | EMR / Glue, subject to job and connector requirements                          |
| Lakehouse             | Iceberg + chosen catalog     | Object storage plus compatible catalog; decide metadata and commit integration |
| Interactive analytics | Trino                        | Self-managed query cluster or evaluated managed alternative                    |
| Orchestration         | Airflow                      | MWAA or self-managed Airflow                                                   |
| Operational metadata  | PostgreSQL                   | RDS                                                                            |
| Serving cache         | Redis                        | Compatible ElastiCache deployment, subject to validation                       |
| Product services      | FastAPI / Next.js            | ECS or EKS; bounded stateless functions only where appropriate                 |
| Metrics / dashboards  | Prometheus / Grafana         | Managed Prometheus / Managed Grafana candidates                                |
| Models                | MLflow and inference runtime | Self-hosted or evaluated managed equivalent                                    |

Kubernetes/Helm and Terraform become deliverables only when real deployment requirements justify them. Snowflake and Databricks remain optional integration studies.

## Production decisions to implement and validate

| Concern           | Proposed direction                                                                                      | Required evidence / open choice                                                 |
| ----------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Data placement    | Durable object storage for landing, lakehouse, checkpoints, and artifacts; metadata in backed-up stores | Retention, isolation, catalog implementation, restore tests                     |
| Networking        | Public ingress only for product routes; private data and control services                               | Network policy, service identity, TLS, restricted egress and administration     |
| Secrets           | Managed secrets and workload identities                                                                 | Rotation and least-privilege permissions; no embedded credentials               |
| Scaling           | Kafka partitions, Flink parallelism, transient Spark capacity, bounded query/service autoscaling        | Load tests including hot keys, rebalances, checkpoint impact, downstream limits |
| Worker failure    | Restart and restore durable state; idempotent retry of batch work                                       | Reconciliation of committed outputs, offsets, and cache state                   |
| High availability | Multi-zone placement and redundant critical services when required                                      | Catalog/DB failover, broker durability, recovery objectives and restore drills  |
| Model serving     | Versioned artifacts and controlled promotion/rollback                                                   | Compatibility, latency, rollback and fallback behavior                          |
| Telemetry         | Central metrics, logs, and exported traces                                                              | Trace backend, retention, sampling, alert ownership                             |

Long-running Kafka/Flink/query services need durable state and steady operational management. Finite Spark jobs, scheduled refreshes, and training are candidates for temporary capacity. Serverless product endpoints require validation of cold starts, connection behavior, timeouts, and model loading.

No RPO, RTO, latency SLO, or availability target has been approved. Define these before choosing topology and replica counts.

## Cost controls

Estimate always-on broker/compute capacity, object storage and requests, scan volume, network/NAT/egress, metadata databases, telemetry retention, training/inference, and LLM usage. Keep the demo bounded, shut down temporary experiments, set budgets, and limit query scans. No monthly estimate is meaningful until region, workload, retention, and availability requirements are chosen.

Before an actual cloud rollout, prove the local data path, select compatible versions, rehearse backup/recovery, measure a representative workload, estimate cost, and document deployment and teardown procedures.

## Public exports and expanded retention

The initial public portal is an export-backed static consumer; see the [portal contract](portal.md). FastAPI, an online database, inference and agent runtimes are added only with features requiring them. The engineering environment and public serving environment have independent lifecycles.

A larger deployment may retain historical releases and ingest the latest published periods continuously through scheduled source discovery. The local 20 GB cap is not a cloud storage or canonical-schema limit. Size historical retention, refresh/backfill concurrency, checkpoints and compute separately; preserve identical identity, correction and publication semantics across profiles. Increasing retention or parallelism must not change what a published count means.
