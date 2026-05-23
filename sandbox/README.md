# Home Assistant Sandbox

Run Home Assistant integrations in isolated subprocesses that connect back to a real HA instance over websocket. The host owns the entity/device registries, areas, and service routing; sandboxed integrations are unaware they're sandboxed.

This directory is the home for all sandbox-related code and docs. It lives on the `sandbox` branch of the [home-assistant/core](https://github.com/home-assistant/core) checkout, alongside the HA Core integration at `../homeassistant/components/sandbox/`.

## Layout

- `hass_client/` — client library (`RemoteHomeAssistant`) plus the sandbox runtime, brought in as a git subtree from [balloob-travel/hass-client](https://github.com/balloob-travel/hass-client).
- `OVERVIEW.md` — high-level architecture: components, service call flow, test infra, supported platforms.
- `ARCHITECTURE.md` — deeper prose on entity proxy mechanics, startup sequence, state sync, registry handling, method compatibility.
- `architecture.html` — visual companion with system diagram, flow diagrams, file structure, websocket API, and test results. Publish via `gh gist create architecture.html` and view at `https://gisthost.github.io/?<gist_id>`.
- `run_all_sandbox_tests.{py,sh}` + `analyze_failures.py` + `TEST_RESULTS.csv` — driver and results for running HA Core's per-integration test suites through the sandbox plugin.
- The HA integration itself is at [`../homeassistant/components/sandbox/`](../homeassistant/components/sandbox/).

## Quick start

```bash
cd core/sandbox/hass_client
uv sync

# Connect a sandbox client to a running HA instance
uv run python -m hass_client.sandbox \
    --url ws://localhost:8123/api/websocket \
    --token <sandbox_token>
```

The `<sandbox_token>` is issued by the host HA when a config entry is marked `options["sandbox"] = "<sandbox_id>"`. The sandbox integration spawns the subprocess and injects the token automatically — you only need to run the client by hand for debugging.

## Running HA Core's tests through the sandbox

```bash
cd core/sandbox/hass_client

# A single integration
uv run python -m pytest -p hass_client.testing.conftest_sandbox \
    ../../tests/components/input_boolean/test_init.py -v

# All currently-passing integrations
uv run python -m pytest -p hass_client.testing.conftest_sandbox \
    ../../tests/components/{input_boolean,automation,script,scene,todo,group}/test_init.py
```

See [`hass_client/SANDBOX_COMPAT.md`](hass_client/SANDBOX_COMPAT.md) for the full compatibility report (33 integrations, 878/880 tests, 99.8% pass rate).

Two pytest plugins are available:

- `hass_client.testing.pytest_plugin` — drop-in `RemoteHomeAssistant`, no websocket. Fast compatibility check.
- `hass_client.testing.conftest_sandbox` — full path: host HA + aiohttp test server + sandbox token + live websocket. Exercises the real deployment.

## Status

33 integrations pass end-to-end through the live websocket. Detailed breakdown in [`hass_client/SANDBOX_COMPAT.md`](hass_client/SANDBOX_COMPAT.md); per-test results in [`TEST_RESULTS.csv`](TEST_RESULTS.csv).
