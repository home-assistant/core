# Command runner for Home Assistant Core development.
#
# Run `just` to list all recipes. The recipes wrap the existing scripts in
# `script/` and the tools we already use, so both keep working as before.
# Python tools run through `uv run --no-sync`, which picks up the virtual
# environment created by `just setup` (or the devcontainer).

set positional-arguments

uv_run := "uv run --no-sync"

# List all available recipes
[private]
default:
    @just --list

# Set up a fresh checkout: virtual environment, dependencies, and a config directory
setup:
    script/setup

# Bring an existing checkout up to date: dependencies and English translations
update:
    {{ uv_run }} script/bootstrap

# Start Home Assistant locally, using the `config` directory
run:
    {{ uv_run }} script/server

# Run the prek hooks on all files, like CI does (pylint and mypy have their own recipes)
lint:
    PREK_SKIP=no-commit-to-branch,mypy,pylint {{ uv_run }} prek run --all-files

# Run ruff and pylint on the Python files changed compared to upstream/dev
lint-changed:
    {{ uv_run }} script/lint

# Run pylint, optionally on specific paths
pylint *paths="homeassistant":
    {{ uv_run }} pylint "$@"

# Run mypy type checking
mypy:
    {{ uv_run }} mypy homeassistant pylint

# Auto-format and auto-fix the code with ruff
format:
    {{ uv_run }} ruff check --fix homeassistant pylint script tests
    {{ uv_run }} ruff format homeassistant pylint script tests

# Run the test suite, optionally with extra pytest arguments or paths
test *args:
    {{ uv_run }} pytest "$@"

# Run the tests of an integration and report its code coverage
coverage integration:
    {{ uv_run }} pytest "tests/components/$1" \
        --cov="homeassistant.components.$1" \
        --cov-report=term-missing \
        --durations-min=1 \
        --durations=0 \
        --numprocesses=auto

# Update the syrupy snapshots of an integration
snapshot-update integration:
    {{ uv_run }} pytest "tests/components/$1" --snapshot-update

# Validate and regenerate integration metadata (manifests, generated files, and more)
hassfest *args:
    {{ uv_run }} python -m script.hassfest "$@"

# Regenerate the requirements files from the integration manifests
gen-requirements:
    {{ uv_run }} python -m script.gen_requirements_all

# Install the requirements of a single integration
install-integration-requirements integration:
    {{ uv_run }} python -m script.install_integration_requirements "$1"

# Compile the English translations for all integrations, or a single one
translations integration="":
    #!/usr/bin/env sh
    set -e
    if [ -z "$1" ]; then
        {{ uv_run }} python -m script.translations develop --all
    else
        {{ uv_run }} python -m script.translations develop --integration "$1"
    fi

# Create a new integration, or add a scaffold (like config_flow) to an existing one
scaffold template="integration" integration="":
    #!/usr/bin/env sh
    set -e
    if [ -z "$2" ]; then
        {{ uv_run }} python -m script.scaffold "$1"
    else
        {{ uv_run }} python -m script.scaffold "$1" --integration "$2"
    fi
