# Contributing to UrbanFlow

The repository contains a Python foundation package and runnable quality tooling. Data pipelines and application services remain planned. Start with [project context](docs/context.md) and the [roadmap](docs/roadmap.md).

## Local setup

Use Node.js 24 (the version in `.node-version`) and npm. From the repository root:

```sh
npm ci
npm run check
```

`npm ci` installs the exact dependency tree from `package-lock.json` and enables the repository's Husky pre-commit hook. Hooks are local to each clone; every contributor needs to run setup. No Python environment or application services are required for these documentation checks.

## Python foundation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv sync --locked
uv run --locked urbanflow check-config --config configs/local.example.toml
npm run check:all
```

The foundation uses Python 3.13, selected by `.python-version`; uv provisions it if necessary. This is the tested package runtime, not a claim of Spark or Iceberg connector compatibility. Dependencies are resolved in `uv.lock`; commit it alongside dependency changes. CI currently uses uv 0.11.8. PostgreSQL access uses the locked Psycopg 3 binary distribution.

For personal settings, copy `configs/local.example.toml` to the ignored `configs/local.toml` and pass that path to `--config`. Relative data paths resolve beside the configuration file. The example uses ignored `.local/data`, a PostgreSQL metadata URL, and decimal-GB budgets: 10 GB routine data, 20 GB peak data and 8 GB stack memory. Set credentials with `URBANFLOW_METADATA_DATABASE_URL` or a local PostgreSQL password file. `check-config` redacts the database URL. The loader rejects unknown/missing settings, invalid budgets and targets above the peak. Budgets remain environment configuration and may differ in an expanded deployment.

`check-config` validates and prints settings, redacting the database URL; it creates no directories, downloads no data and starts no services. Admission control, free-space measurement and container memory enforcement are future implementation work. Keep database credentials in environment variables or a local PostgreSQL password file, not in the committed example profile.

To download one monthly NYC TLC Yellow Taxi source file, set `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD` in the ignored `.env`, then start PostgreSQL with `docker compose up -d postgres`. Compose reads `.env` for the container; the Python client needs the same password through `PGPASSWORD`, `URBANFLOW_METADATA_DATABASE_URL`, or a local PostgreSQL password file. Use a personal profile:

```sh
uv run --locked urbanflow download-yellow-taxi --config configs/local.toml --period 2024-01
```

The command writes the raw file under the configured data directory and acquisition metadata to PostgreSQL. A repeat run uses the recorded local release; add `--refresh` to fetch the source again and observe corrections. Download success does not validate trip rows or publish an analytical table. Use a small period only when there is enough local disk space for the source file and any retained releases.

Current code lives in `src/urbanflow/config/`, `src/urbanflow/database/`, `src/urbanflow/ingestion/`, and the CLI; tests live in `tests/unit/`. Create lakehouse and service directories when their first implementation arrives. The wider HTML folder tree remains a proposal.

## Standard checks

| Command                 | Purpose                                               |
| ----------------------- | ----------------------------------------------------- |
| `npm run format`        | Apply Prettier to supported repository files          |
| `npm run format:check`  | Check formatting without changing files               |
| `npm run lint:md`       | Check Markdown with markdownlint-cli2                 |
| `npm run lint:html`     | Check the public HTML guides with HTMLHint            |
| `npm run check`         | Run all of the above checks without formatting writes |
| `npm run format:python` | Format Python with Ruff                               |
| `npm run check:python`  | Check Python formatting/lint and run pytest           |
| `npm run check:all`     | Run documentation/configuration and Python checks     |
| `uv build`              | Build the Python source distribution and wheel        |

The pre-commit hook uses lint-staged to format and lint staged files, including Python through locked Ruff. Python commits require uv and the synced environment. It adds formatter changes to the commit and stops on lint failures. CI checks documentation and Python formatting/linting, config validation and a package build on pull requests and pushes to `main`. CI does not run pytest; run the local Python check command when validating behavior changes. CI never autoformats files.

Prettier also parses supported JSON/YAML configuration and embedded CSS/JavaScript in HTML. HTMLHint checks basic structure, duplicate IDs/attributes, titles and image alternative text. SVG attribute casing is allowed because the architecture guide contains inline SVG. Markdown line length is unrestricted to keep prose and tables readable in source; Prettier owns table formatting. Raw `docs/internal/` inputs and vendored diagram logos are excluded from formatting. Internal inputs are also excluded from Markdown linting and remain ignored by Git.

These checks do not validate architecture correctness, dataset semantics, browser layout, accessibility comprehensively, or link destinations. Review those concerns separately. Do not claim a browser test passed when browser access was unavailable.

## Agent skills

Project instructions live in `AGENTS.md`. Two repository-scoped skills live under `.agents/skills/`:

- `urbanflow-design`: architecture, decisions and guide consistency.
- `urbanflow-pipelines`: source contracts, idempotency, refresh/backfill and publication correctness.

They reference the maintained design docs instead of copying the entire architecture. They contain no custom lint scripts. Their YAML frontmatter and Markdown are covered by normal formatting/linting; the skill-creator's supplied validator can additionally check skill metadata during skill authoring.

## Add checks with implementation

Ruff formatting/linting and local pytest checks cover the foundation package. Introduce TypeScript/ESLint and appropriate UI tests with the portal, and dbt compilation/data tests with SQL models. Keep full datasets, load tests and cloud experiments out of the default CI job.

Add CI services only for integration tests that need them. Pin dependencies, preserve lockfiles, and document the local command that matches each CI job. Dependabot proposes npm and GitHub Actions updates weekly. The workflow uses read-only repository permissions and commit-pinned actions.

A passing workflow becomes enforceable only after a repository administrator makes its job a required branch-protection check. This change does not configure remote branch protection or deploy anything.
