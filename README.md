# UrbanFlow

A planned open-source mobility lakehouse for historical and latest published data, streaming replay, distributed analytics, forecasting and grounded natural-language tools.

**Status:** architecture documentation, repository quality tooling and a Python foundation package with local configuration validation. Ingestion, lakehouse services and the portal remain planned.

With Node.js 24 and [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```sh
npm ci
uv sync --locked
uv run --locked urbanflow check-config --config configs/local.example.toml
npm run check:all
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, formatting, linting, pre-commit hooks and CI. Project-specific agent guidance lives in [AGENTS.md](AGENTS.md).

Read the [plain-language project guide and proposed folder structure](docs/project-guide.html) for an approachable explanation of what we will build and a layout you can comment on.

Start with the [documentation](docs/README.md), [contributor context](docs/context.md), [platform architecture](docs/architecture/platform.md) and [delivery roadmap](docs/roadmap.md).

Open the [interactive HTML architecture review](docs/diagrams/architecture.html) in a browser for the supplied visual design, adapted to the reconciled architecture. No server or installation is needed. The [diagram guide](docs/diagrams/README.md) also preserves the earlier technology atlas and editable draw.io views.

The system is modular for expansion. Its first local deployment targets a bounded working set on a 16 GB machine, with reproducible historical analysis and ongoing source refresh sharing explicit contracts.
