# UrbanFlow documentation

UrbanFlow is a planned open-source urban mobility platform combining a lakehouse, streaming and batch processing, forecasting, anomaly detection, and tool-grounded analytics.

**Status:** design documentation. The repository currently has no application, infrastructure, pipelines, trained models, or measured benchmarks. Components and interfaces below are targets, not deployed capabilities. No setup commands are presented as runnable.

## Reading guide

| Document | Covers |
| --- | --- |
| [Plain-language project guide](project-guide.html) | What we will build, how data moves, proposed folder structure and feedback questions |
| [Contributor / agent context](context.md) | Current baseline, constraints, reading order and next work |
| [Historical and latest data](architecture/data-lifecycle.md) | Release discovery, corrections, backfills, publication and retention |
| [One-trip walkthrough](architecture/one-trip.md) | Physical representations and end-to-end evidence |
| [Public portal](architecture/portal.md) | Export contract, first pages and runtime expansion |
| [Benchmark protocol](operations/benchmarks.md) | Fair comparisons, bounded experiments and report requirements |
| [Source reconciliation](decisions/source-reconciliation.md) | What changed, what was preserved and what stays out of scope |
| [Project overview](overview.md) | Product goals, scope, principles, and workload tiers |
| [Platform architecture](architecture/platform.md) | Components, data paths, boundaries, and technology scope |
| [Data model and contracts](data-model/contracts.md) | Sources, canonical fields, lakehouse tables, quality, and replay |
| [ML, API, and analytics agent](architecture/ml-and-serving.md) | Forecasting, evaluation, serving, and tool security |
| [Local deployment](architecture/local.md) | Proposed Compose profiles and developer workflow |
| [Cloud deployment](architecture/cloud.md) | Public demo and production deployment design |
| [Reliability and operations](operations/reliability.md) | Observability, failure experiments, runbooks, testing, and benchmarks |
| [Architecture decisions](decisions/README.md) | Design rationale, source reconciliation, and unresolved choices |
| [Delivery roadmap](roadmap.md) | Eight stages and evidence needed to complete each |
| [Editable diagrams](diagrams/README.md) | Three native draw.io architecture files |
| [Interactive architecture review](diagrams/architecture.html) | Adapted supplied HTML: clickable pipeline, one-trip journey, resource policy and decision gates; opens directly in a browser |

## Basis and interpretation

These documents reconcile the original specification, tools/technology and deployment notes with the newly supplied GPT context and HTML architecture review. Internal sources stay unchanged and excluded from Git; public documentation is self-contained. Read the [source reconciliation](decisions/source-reconciliation.md) for conflict resolutions and excluded material.

The architecture supports historical backfills and latest-source refresh, with modular boundaries for expansion. The current local profile has a 20 GB peak working-data ceiling; it does not cap the overall architecture. All components, software compatibility, resource estimates and cloud mappings remain design intent until tested. Discovery URLs are not proof of current availability or approved versions.
