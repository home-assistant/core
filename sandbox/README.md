# Home Assistant Sandbox

A fresh rewrite of the sandbox system that runs Home Assistant
integrations in isolated subprocesses while the main instance keeps a
single, unified view of devices, entities, services, and events.

v1 (`../sandbox/` plus `../homeassistant/components/sandbox/`) is kept
around for reference and comparison until v2 has matched v1's compat
numbers and shipped at least one stable release. See
[`OVERVIEW.md`](OVERVIEW.md) for the full architecture and
[`plan.md`](plan.md) for the phase-by-phase task list.

## Layout

- `hass_client/` — Python client library (its own `uv` env). Hosts the
  `SandboxRuntime`, the entity / service / event bridges, the
  `RemoteStore`, and the two pytest plugins.
- `docs/` — design decisions captured per phase:
  - [`entity-bridge-decision.md`](docs/entity-bridge-decision.md) —
    Option A vs Option B (the Phase 1 spike). Option B shipped.
  - [`auth-scoping-decision.md`](docs/auth-scoping-decision.md) — why
    `scopes` lives on `RefreshToken` itself and how the dispatcher
    enforces it (Phase 7).
- `plan.md` — the implementation plan that drives this work.
- `OVERVIEW.md` — architecture document.
- `STATUS-phase-N.md` — per-phase landing notes: what each phase
  built, what it deferred, what it flagged forward.
- `run_compat.py` + `COMPAT.md` — compat-lane runner and report.

The HA Core side of the integration lives at
[`../homeassistant/components/sandbox/`](../homeassistant/components/sandbox/).

## Quick start

```bash
cd sandbox/hass_client
uv sync
uv run pytest

# Run the runtime by hand against a local HA (debugging only — the
# manager normally spawns the subprocess for you).
uv run python -m hass_client.sandbox \
    --name built-in \
    --url ws://localhost:8123/api/websocket \
    --token <scoped sandbox token>
```

In production, the integration creates the system user, issues the
scoped token, and spawns the subprocess automatically once the first
flow or entry routes to a given group. The `<scoped sandbox token>`
above is the credential `sandbox/auth.py` mints; running the
runtime by hand requires creating one yourself.

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

[`COMPAT.md`](COMPAT.md) is the compat-lane report; per-failure
output lands in `${SANDBOX_V2_ERRORS_DIR:-/tmp/sandbox_errors}`.

## Status

Phases 0–17 landed:

- **Phase 0** — skeletons in place. Empty HA integration loads.
- **Phase 1** — entity-bridge spike. Recommendation:
  [Option B (action-call forwarding)](docs/entity-bridge-decision.md).
- **Phase 2** — runtime classifier (`classify(integration)`).
  Computes routing from manifest + platform inspection, no user
  config.
- **Phase 3** — sandbox lifecycle. `SandboxManager` spawns one
  subprocess per group lazily; restart-on-crash with budget.
- **Phase 4** — config-flow forwarding. New flows run inside the
  sandbox; main owns the canonical `ConfigEntry` store.
- **Phase 5** — entity bridge end-to-end. Four initial proxies
  (`light`, `switch`, `sensor`, `binary_sensor`); per-loop-tick
  fan-out batching; exception translation. The remaining 28
  domain proxies landed in **Phase 13**.
- **Phase 6** — service & event mirroring. Sandbox-side
  `ServiceMirror` + `EventMirror` push registrations and events to
  main, gated by a refcounted `ApprovedDomains` set.
- **Phase 7** — scoped auth (`RefreshToken.scopes`) + opt-in data
  sharing (`SandboxGroupConfig`). Sandbox tokens reject every
  non-`sandbox/*` command at the dispatcher.
- **Phase 8** — `Store` routing. `RemoteStore` proxies every
  `Store(...)` in the sandbox to
  `<config>/.storage/sandbox/<group>/<key>` on main.
- **Phase 9** — graceful shutdown + restore-state hand-off. Sandboxes
  unload entries and dump `RestoreEntity` state into the shutdown
  reply; main persists it for the next boot's warm-load.
- **Phase 10** — test infrastructure. Two pytest plugins (in-process
  + real-subprocess) plus the [`run_compat.py`](run_compat.py)
  runner.
- **Phase 11** — docs & cleanup. [`OVERVIEW.md`](OVERVIEW.md),
  [`docs/auth-scoping-decision.md`](docs/auth-scoping-decision.md),
  and the directory-local [`CLAUDE.md`](CLAUDE.md).
- **Phase 12** — concurrent channel dispatcher; closes Phase 9's
  reentrancy deadlock and fires `EVENT_HOMEASSISTANT_FINAL_WRITE`
  on sandbox shutdown.
- **Phase 13** — remaining 28 domain proxies; all 32 supported HA
  entity domains now have a typed proxy.
- **Phase 14** — `data_schema` + service-schema marshalling,
  `unique_id` propagation, `async_unload_entry` core hook,
  200-light area-call perf benchmark.
- **Phase 15** — v1-baseline compat sweep against the 37-integration
  list (99.19 % at the time; lifted to 99.97 % by Phase 17).
- **Phase 16** — cross-integration sweep across 807 integrations
  (98.07 %), categorised backlog ([`BACKLOG.md`](BACKLOG.md)).
- **Phase 17** — `ConfigEntry.sandbox` first-class field; closed
  552 of 664 known failures and lifted the full-sweep test-level
  pass rate from 98.07 % to **99.67 %** (above the 99.5 %
  v1-removal threshold).

The per-phase `STATUS-phase-N.md` files are the authoritative record
of what each phase actually built, what it deferred, and what it
flagged forward; [`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md) tells the
narrative story of Phases 12–17 (what each one's predecessor
flagged, what landed, the outcome).
