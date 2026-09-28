# CI/CD Pipeline Pack (3x)

This folder provides the same workflow design in three CI/CD systems, each with:

1. A base pipeline configuration.
2. A modified workflow for system-specific requirements.
3. A short explanation of how and why the modified workflow differs.

## 1) GitHub Actions

- Base: `github-actions.base.yml`
- Modified: `github-actions.custom.yml`

### What the base config does

- Triggers on push to main and pull requests.
- Tests against Python 3.12 and 3.13 with a matrix.
- Caches pip dependencies.
- Runs linting (`ruff`) and tests (`pytest`).

### Why the modified workflow is different

Use the custom version when your system:

- Requires self-hosted runners.
- Needs Docker-based integration tests.
- Needs a split between lint and integration phases.

Changes made:

- Replaced `ubuntu-latest` with `self-hosted`.
- Split jobs into `lint` and `integration-tests`.
- Added `docker compose` test execution and cleanup.

## 2) GitLab CI

- Base: `.gitlab-ci.base.yml`
- Modified: `.gitlab-ci.custom.yml`

### What the base config does

- Defines `lint` and `test` stages.
- Uses Python 3.13 image.
- Caches pip downloads.
- Runs lint and unit tests.

### Why the modified workflow is different

Use the custom version when your system:

- Runs on tagged runners (for example Docker-capable runners).
- Requires service containers (like PostgreSQL).
- Needs a packaging stage with artifacts.

Changes made:

- Added `default.tags` to target specific runners.
- Added PostgreSQL service and env vars for recorder-focused tests.
- Added `package` stage and `dist/` artifact publishing.

## 3) Azure Pipelines

- Base: `azure-pipelines.base.yml`
- Modified: `azure-pipelines.custom.yml`

### What the base config does

- Triggers on main for both CI and PR.
- Runs on Microsoft-hosted Ubuntu.
- Uses a Python matrix (3.12, 3.13).
- Runs lint and tests.

### Why the modified workflow is different

Use the custom version when your system:

- Uses a self-hosted pool.
- Needs integration tests using Docker compose.
- Publishes build artifacts only from main.

Changes made:

- Switched pool from hosted image to `SelfHostedLinux`.
- Split work into staged jobs (`LintAndTests`, `Publish`).
- Added gated artifact publication stage for `main` branch only.

---

These files are intentionally isolated from the repository's current CI setup so you can evaluate or adopt them independently.
