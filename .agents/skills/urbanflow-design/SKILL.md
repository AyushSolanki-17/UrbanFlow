---
name: urbanflow-design
description: Reconcile UrbanFlow architecture decisions, scope, roadmap and public Markdown/HTML guides. Use for design changes or architecture reviews, not routine formatting-only edits.
---

# UrbanFlow design

Work from the repository root. Read `docs/context.md`, then the affected architecture page and `docs/decisions/README.md`. For conflicts with raw notes, consult `docs/decisions/source-reconciliation.md`; do not load all internal conversations by default.

## Reconcile before expanding

- Preserve explicit user constraints and useful existing scope. Separate an accepted design direction, an implementation choice still requiring a compatibility test, and a capability demonstrated by code/evidence.
- Local limits constrain the local profile, not the canonical schema or overall architecture. Keep endpoints, retention, source periods and concurrency configurable.
- Preserve both historical analysis and latest-published-source refresh. Historical replay is a separate simulation; neither it nor a new published trip file proves live data availability.
- Give every new component a distinct responsibility, stage and acceptance condition. Do not promote tools from the learning inventory into dependencies without a concrete workload.
- Keep one owner per table/product. Changes to Spark, dbt or Flink ownership need an explicit transfer or reconciliation rule.

## Update the affected surfaces

Change the relevant contract/architecture page first, then its decision record and roadmap evidence when needed. Update `docs/context.md` only when the baseline changes. Keep `docs/project-guide.html` approachable and its folder tree labelled as proposed until implementation creates it. Keep `docs/diagrams/architecture.html` consistent with canonical table names and responsibilities. Earlier reference diagrams/atlas must not be presented as the current implementation.

Use Prettier, markdownlint and HTMLHint through `npm run check`; see `CONTRIBUTING.md`. Do not replace them with a custom validator script. Inspect HTML in a permitted browser when visual changes warrant it, and state the limitation if only static checks were possible.

Report the design outcome, remaining decisions and actual validation. Documentation alone does not establish engine compatibility, measured resource use, performance or cloud cost.
