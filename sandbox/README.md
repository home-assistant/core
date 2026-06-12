# Home Assistant Sandbox

Runs Home Assistant integrations in isolated subprocesses while the main
instance keeps a single, unified view of devices, entities, services, events,
and translations — as if everything ran locally.

- **[`ARCHITECTURE.md`](ARCHITECTURE.md)** — the full architecture: routing,
  lifecycle, config-flow forwarding, entity bridge, service/event mirror, store
  routing, translations, auth, shutdown, and the core-HA touch surface. Start
  here.
- **[`CLAUDE.md`](CLAUDE.md)** — orientation for working in this directory:
  repository layout, the core-HA files modified, open follow-ups, and how to run
  the tests.
- **[`docs/`](docs/)** — per-decision design write-ups (entity-bridge spike,
  state-sharing design, query-shaped RPCs, …).
- **[`status/`](status/)** — per-phase / per-plan landing notes: the
  authoritative record of what each phase shipped, deferred, and flagged
  forward.

## Layout

- `hass_client/` — the Python client library (its own `uv` env). Hosts
  `SandboxRuntime`, the flow / entity / service / event runners, the
  channel-backed store bridge, and the two pytest plugins. Also carries the
  runtime's Docker test image (see
  [`hass_client/docs/docker.md`](hass_client/docs/docker.md)).
- `run_compat.py` + `COMPAT.md` / `BACKLOG.md` — compat-lane runner and curated
  reports.

The HA Core side of the integration lives at
[`../homeassistant/components/sandbox/`](../homeassistant/components/sandbox/).

## Quick start

```bash
cd sandbox/hass_client
uv sync
uv run pytest

# Run the runtime by hand against a local HA (debugging only — the manager
# normally spawns the subprocess for you, over stdio).
uv run python -m hass_client.sandbox --name built-in --url stdio://
```

The runtime holds no credential: it never opens a connection back to main and
never acts on main's behalf (see [`ARCHITECTURE.md`](ARCHITECTURE.md) §10). In
production the integration spawns the subprocess automatically once the first
flow or entry routes to a given group; `--url` selects the transport
(`stdio://` default, `unix://<path>` opt-in; `ws://` is reserved and not yet
implemented).

## Running HA Core's tests through the sandbox

```bash
# In-process plugin (fast, freezer-safe)
cd sandbox/hass_client
uv run python -m pytest -p hass_client.testing.pytest_plugin \
    ../../tests/components/input_boolean/test_init.py -v

# Real-subprocess plugin (pins the subprocess boundary)
uv run python -m pytest -p hass_client.testing.conftest_sandbox \
    ../../tests/components/input_boolean/test_init.py -v

# Or drive the compat lane runner
cd sandbox
python run_compat.py input_boolean light switch
```

[`COMPAT.md`](COMPAT.md) is the curated compat-lane report; per-failure output
lands in `${SANDBOX_ERRORS_DIR:-/tmp/sandbox_errors}`.

## Status

Phases 0–20 plus the boundary-hardening closing batch have landed: the
concurrent channel dispatcher, all 31 domain proxies, schema / `unique_id` /
unload-hook marshalling, the `ConfigEntry.sandbox` first-class field,
device-registry bridging, the protobuf wire with pluggable transports, stateless
sha-pinned integration sources, translation forwarding, and the request/response
query RPCs. The [`ARCHITECTURE.md`](ARCHITECTURE.md) changelog summarises the
closing batch; [`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md) tells the narrative; the
[`status/`](status/) landing notes are the authoritative per-phase record.

What's still open is tracked in [`ARCHITECTURE.md`](ARCHITECTURE.md) §14 (and
`CLAUDE.md`): the state-sharing subscription consumer, query-shaped
subscriptions/push, cross-sandbox in-process dependencies, and pip/egress
validation for containerised custom-integration dependencies.
