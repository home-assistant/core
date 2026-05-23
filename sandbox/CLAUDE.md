# Home Assistant Sandbox

This project implements a sandbox system for Home Assistant, allowing integrations to run in isolated processes that connect back to a real HA instance.

All sandbox-specific code and docs live under this directory (`core/sandbox/`) on the `sandbox` branch of the core checkout. The only piece outside this directory is the HA Core integration itself at `homeassistant/components/sandbox/`, which has to live there for HA's integration loader to find it.

## Architecture

See [OVERVIEW.md](OVERVIEW.md) for the full architecture document.

## Repository Layout

This directory (`core/sandbox/`) holds everything sandbox-related:

- `hass_client/` — Client library that provides `RemoteHomeAssistant`, a HA subclass connected to a real HA via websocket. Extended with sandbox mode for running integrations out-of-process. Brought in as a git subtree from `balloob-travel/hass-client`.
- `ARCHITECTURE.md`, `OVERVIEW.md` — design docs.
- `analyze_failures.py`, `run_all_sandbox_tests.{py,sh}`, `TEST_RESULTS.csv` — test driver and results for running HA Core's integration test suites through the sandbox.
- `architecture.html` — rendered architecture diagram (publishable via `gh gist create`, see below).

The HA Core integration lives at `../homeassistant/components/sandbox/` (one level up).

## Key Concepts

- **Sandbox integration** (`../homeassistant/components/sandbox/`): HA Core integration that manages sandboxed config entries, creates auth tokens, spawns sandbox processes, and exposes a websocket API for sandbox clients.
- **Sandbox token**: A system-generated auth token scoped to a specific sandbox instance. Only connections with a sandbox token can access the `sandbox/*` websocket commands.
- **Sandbox client** (`hass_client/hass_client/sandbox.py`): Extends `RemoteHomeAssistant` to fetch config entries from the sandbox API, set up integrations locally, and push entities/state back to HA Core.

## Development

`hass_client/` has its own Python environment (managed with `uv`). It depends on HA Core packages, and `hass_client/pyproject.toml` uses `[tool.uv.sources]` to link `homeassistant` to the surrounding core checkout (`../..`).

To run the sandbox client:
```
python -m hass_client.sandbox --url ws://localhost:8123/api/websocket --token <sandbox_token>
```

## Testing

### Running core integration tests through the sandbox

Two pytest plugins let us run HA Core's own test suites against the sandbox infrastructure:

1. **Base plugin** (`-p hass_client.testing.pytest_plugin`): Replaces `HomeAssistant` with `RemoteHomeAssistant` as a drop-in. No real websocket — tests the client library's compatibility layer. Fast but doesn't exercise the real network path.

2. **Sandbox plugin** (`-p hass_client.testing.conftest_sandbox`): Boots a host HA Core with `websocket_api` + `sandbox`, starts a real aiohttp test server, creates a sandbox auth token, and connects the sandbox `RemoteHomeAssistant` to it via a live websocket. Tests run exactly as they would in a real sandbox deployment.

```bash
cd core/sandbox/hass_client
# Run a single integration
uv run python -m pytest -p hass_client.testing.conftest_sandbox \
    ../../tests/components/input_boolean/test_init.py -v

# Run all passing integrations
uv run python -m pytest -p hass_client.testing.conftest_sandbox \
    ../../tests/components/{input_boolean,automation,script,scene,todo,group}/test_init.py
```

See `hass_client/SANDBOX_COMPAT.md` for the full compatibility report (33 integrations, 99.8% pass rate).

### Key test infrastructure details

- **Socket bypass**: Core's `pytest-socket` blocks real sockets. The sandbox plugin saves the real socket class at configure time and restores it during the sandbox context manager.
- **Freezer fallback**: Tests using `freezer.move_to()` (pytest-freezer) hang with live websocket connections. The sandbox plugin detects the `freezer` fixture and falls back to the base plugin for those tests.
- **Host HA lifecycle**: The sandbox plugin creates two HA instances per test (host + sandbox). The host is explicitly stopped in teardown to cancel its timers and prevent `verify_cleanup` errors.
- **HybridServiceRegistry**: `RemoteHomeAssistant` uses `HybridServiceRegistry` which tries local services first, then falls back to remote. The fallback only triggers for services that exist in the remote service cache.

## Publishing HTML Files

Upload an HTML file as a private GitHub Gist, then it's viewable at `https://gisthost.github.io/?<GIST_ID>`.

```bash
gh gist create architecture.html
# Returns gist ID → site is at https://gisthost.github.io/?<ID>
```

## Current State

33 integrations pass through the real sandbox websocket (878/880 tests). See `hass_client/SANDBOX_COMPAT.md` for details.
