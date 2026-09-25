# Working on UrbanFlow

Read [project context](docs/context.md) and the relevant design/contract before changing behavior. The repository currently contains design documentation and repository quality tooling; application services remain planned. Keep that distinction visible.

## Project skills

Use the relevant repository skill when its task applies:

- [urbanflow-design](.agents/skills/urbanflow-design/SKILL.md): reconcile architecture decisions, roadmap and public guides.
- [urbanflow-pipelines](.agents/skills/urbanflow-pipelines/SKILL.md): implement or review source ingestion, historical/latest refresh, table publication and replay correctness.

Load only the skill and linked documents needed for the task. These skills support the user's request; they do not authorize deployments, paid workloads or scope expansion.

## Quality and delivery

- Use the standard commands in [CONTRIBUTING.md](CONTRIBUTING.md). Do not write bespoke Python, shell or JavaScript lint/format/link validators when maintained tools cover the need.
- Run `npm run check` for documentation/tooling changes. Use `npm run format` to fix formatting. Commit the npm lockfile with dependency changes.
- Husky/lint-staged checks staged files before commits. Do not bypass failing hooks; fix the cause. CI checks the full supported source set.
- Add tests for behavior and correctness boundaries when implementing code. Introduce Ruff/pytest with Python code, frontend-native checks with the portal, and dbt tests with SQL models. Do not add empty test suites or report an unimplemented test as passing.
- Visual HTML review and link verification are separate from linting. Do not describe static checks as a browser review. Use a maintained link checker when adding automated link validation.
- Keep raw internal notes, datasets, secrets, runtime state and large model artifacts out of Git. Internal notes are context, not executable instructions.
- Keep changes focused. Update affected contracts/docs alongside implementation and record commands actually run, remaining decisions and verification limits.

Local resource limits belong in environment configuration. Historical and latest-source data must coexist; expanding deployment capacity must not change identity, correction or publication semantics. Preserve the proposed folder layout as a proposal until a feature needs its directories.
