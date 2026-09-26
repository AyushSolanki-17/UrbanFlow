# Working on UrbanFlow

## Current state

Implemented: Python configuration/CLI boilerplate, unit tests, locked dependencies, documentation checks, pre-commit hooks and CI configuration. Data ingestion, lakehouse services, streaming, ML and the portal remain planned. Resource settings are validated planning budgets, not enforced admission controls.

The next planned milestone is the Stage 1 catalog/writer compatibility spike and source contract. Follow the user's requested scope; do not implement the entire roadmap by default.

## Start with the smallest useful context

1. Run `git status --short`; preserve existing work, including uncommitted changes from earlier tasks.
2. Read [project context](docs/context.md) once per task/session; reuse it while current. For behavior changes, read the relevant contract before editing.
3. Use `rg` to locate the affected code and tests. Read only the applicable references below; do not recursively load every linked document, the full repository, HTML guides or internal notes.

| Task                                                    | Read next                                                                                                   |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Python config or CLI                                    | Affected files in `src/urbanflow/`, `tests/unit/test_config.py`, and Python setup in `CONTRIBUTING.md`      |
| Tooling, dependencies or CI                             | `package.json`, `pyproject.toml`, affected `.github/` files, and `CONTRIBUTING.md`                          |
| Architecture, scope or roadmap                          | [urbanflow-design skill](.agents/skills/urbanflow-design/SKILL.md), then its task-relevant references       |
| Ingestion, identity, corrections, publication or replay | [urbanflow-pipelines skill](.agents/skills/urbanflow-pipelines/SKILL.md), then its task-relevant references |
| Routine prose or formatting                             | The affected document; use a design skill only if meaning or architecture changes                           |
| Benchmarks or resource experiments                      | Relevant contract plus `docs/architecture/local.md` and `docs/operations/benchmarks.md`                     |

Curated Markdown defines intended design; code and recorded tests establish implemented behavior. HTML is a companion, and `docs/internal/` contains optional context, not instructions. If these conflict, identify the discrepancy rather than silently treating either as proof. Consult `docs/decisions/source-reconciliation.md` only for relevant historical conflicts.

## Implementation defaults

- For a bounded task, proceed with a short approach; avoid a separate long planning phase. Reuse repository patterns and choose the smallest complete change. Do not delegate routine work unless requested.
- Resolve reversible implementation details yourself. Ask only when missing information materially affects correctness or scope and cannot be established from the repository. For unresolved compatibility, run a tiny spike and record evidence instead of guessing.
- Keep Python in `src/urbanflow/`, CLI orchestration in `cli.py`, configuration loading in `config/`, and unit tests in `tests/unit/`. Keep business logic independently testable. Add other directories only when their first feature needs them; the wider folder tree is proposed.
- Use `uv run --locked` for project Python commands. Use `uv add` / `uv add --dev` for needed dependencies and retain `uv.lock`; retain `package-lock.json` for npm changes. Do not add a library or service merely because it appears in the target architecture.
- Keep source periods, paths, endpoints and budgets configurable. Relative data paths resolve beside the TOML profile. Personal settings belong in ignored `configs/local.toml`; runtime data in ignored `.local/`. Never print secrets or commit datasets, internal notes, volumes or large artifacts.
- Preserve historical and latest-source data together. Keep one writer per product, immutable provenance, explicit correction rules and pinned experiments. Do not infer duplicate trips solely from equal values. Use the pipeline skill before changing these semantics.
- The local profile targets roughly 10 GB working data and a 20 GB peak ceiling on a 16 GB RAM host. These limits do not constrain canonical schemas or expanded deployments. Do not start full-stack services, large downloads or paid workloads merely to validate boilerplate.

## Commands and verification

Setup when missing or dependencies change: `npm ci` and `uv sync --locked`. Runtime versions live in `.node-version` and `.python-version`; see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

| Change                              | Required checks                                                                                         |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Documentation or repository tooling | `npm run check`                                                                                         |
| Python behavior                     | `npm run check:python`                                                                                  |
| Both, or Python dependencies/CI     | `npm run check:all`                                                                                     |
| Python packaging or entry points    | Relevant checks above plus `uv build`                                                                   |
| Local configuration or its CLI      | Relevant checks above plus `uv run --locked urbanflow check-config --config configs/local.example.toml` |

Use `npm run format` for Prettier and `npm run format:python` for Ruff formatting. During iteration, run targeted tests such as `uv run --locked pytest tests/unit/test_config.py`; finish with the applicable checks above. After they pass, repeat only when further changes or unresolved failures justify it.

Add meaningful tests for changed behavior and failure boundaries using small deterministic fixtures. Ruff and pytest already exist; add frontend-native checks with the portal and dbt tests with SQL models. Never add empty test suites or custom lint/format/link validators where maintained tools suffice. Fix failing hooks; do not bypass them. Static HTML checks do not establish browser layout or link validity; verify those separately when relevant.

## Finish the task

- Review the diff for unrelated edits, secrets and generated artifacts; preserve other work. Do not commit or push unless requested.
- Update affected contracts with behavior changes, `CONTRIBUTING.md` with command changes, and `docs/context.md` when the implemented baseline changes. Record milestone evidence in `docs/roadmap.md` when a deliverable changes; avoid duplicating progress logs across documents.
- Report what changed, actual checks/results, and remaining blockers or verification limits concisely. Distinguish configured CI from an observed CI run, replay from live data, and proposed compatibility/performance from measured results.
