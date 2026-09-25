# Contributing to UrbanFlow

The application is still in design. This repository now has runnable quality tooling for its Markdown, HTML and configuration files. Start with [project context](docs/context.md) and the [roadmap](docs/roadmap.md).

## Local setup

Use Node.js 24 (the version in `.node-version`) and npm. From the repository root:

```sh
npm ci
npm run check
```

`npm ci` installs the exact dependency tree from `package-lock.json` and enables the repository's Husky pre-commit hook. Hooks are local to each clone; every contributor needs to run setup. No Python environment or application services are required for these documentation checks.

## Standard checks

| Command                | Purpose                                               |
| ---------------------- | ----------------------------------------------------- |
| `npm run format`       | Apply Prettier to supported repository files          |
| `npm run format:check` | Check formatting without changing files               |
| `npm run lint:md`      | Check Markdown with markdownlint-cli2                 |
| `npm run lint:html`    | Check the public HTML guides with HTMLHint            |
| `npm run check`        | Run all of the above checks without formatting writes |

The pre-commit hook uses lint-staged to format and lint staged files. It adds formatter changes to the commit and stops on lint failures. CI uses the same tool versions and checks the full repository scope on pull requests and pushes to `main`. CI never autoformats files.

Prettier also parses supported JSON/YAML configuration and embedded CSS/JavaScript in HTML. HTMLHint checks basic structure, duplicate IDs/attributes, titles and image alternative text. SVG attribute casing is allowed because the architecture guide contains inline SVG. Markdown line length is unrestricted to keep prose and tables readable in source; Prettier owns table formatting. Raw `docs/internal/` inputs and vendored diagram logos are excluded from formatting. Internal inputs are also excluded from Markdown linting and remain ignored by Git.

These checks do not validate architecture correctness, dataset semantics, browser layout, accessibility comprehensively, or link destinations. Review those concerns separately. Do not claim a browser test passed when browser access was unavailable.

## Agent skills

Project instructions live in `AGENTS.md`. Two repository-scoped skills live under `.agents/skills/`:

- `urbanflow-design`: architecture, decisions and guide consistency.
- `urbanflow-pipelines`: source contracts, idempotency, refresh/backfill and publication correctness.

They reference the maintained design docs instead of copying the entire architecture. They contain no custom lint scripts. Their YAML frontmatter and Markdown are covered by normal formatting/linting; the skill-creator's supplied validator can additionally check skill metadata during skill authoring.

## Add checks with implementation

Introduce Ruff formatting/linting and pytest when Python modules arrive; TypeScript/ESLint and appropriate UI tests with the portal; and dbt compilation/data tests with SQL models. Use tiny deterministic fixtures for pull-request tests. Keep full datasets, load tests and cloud experiments out of the default CI job.

Add CI services only for integration tests that need them. Pin dependencies, preserve lockfiles, and document the local command that matches each CI job. Dependabot proposes npm and GitHub Actions updates weekly. The workflow uses read-only repository permissions and commit-pinned actions.

A passing workflow becomes enforceable only after a repository administrator makes its job a required branch-protection check. This change does not configure remote branch protection or deploy anything.
