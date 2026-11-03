# Hassfest package

Hassfest is split between this package and the
[Core scripts](../../script/hassfest/AGENTS.md).

The intended split is:

- `packages/hassfest`: the shared runner, integration validation that applies to
  both Core and custom integrations, and custom-integration-specific validation.
- `script/hassfest`: Core-only validators and generators, plus the Core entry point
  that selects plugins and invokes the package's runner.

The split is still in progress. Validators that mix shared checks with Core
policies or generation stay in `script/hassfest` until those responsibilities are
separated. Move only the shared or custom-integration logic into this package.
The package must not import from `script`; Core supplies its plugins to the runner.
