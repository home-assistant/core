# STATUS — plan-fidelity-batch

All six fidelity items (#2, #7, #5, #6, #4) plus the appendix lockdown
(point 1) landed as independent commits on branch `sandbox`, each passing
the relevant test suites; a final commit ticks the tracker, sweeps the
docs, and adds this STATUS file.

## Commits (in landing order)

| # | SHA | Subject |
|---|-----|---------|
| 1 (#2) | `969834845b4` | sandbox_v2: rename CLI flag --group to --name (fidelity #2) |
| 2 (#7) | `fd05b17a25b` | sandbox_v2: reconstruct vol.Invalid across the bridge (fidelity #7) |
| 3 (#5) | `3833290b165` | sandbox_v2: prefix proxy entity unique_id with source domain (fidelity #5) |
| 4 (#6) | `c5c7e4adcb5` | sandbox_v2: make register_entity an idempotent upsert (fidelity #6) |
| 5 (#4) | `94804369825` | sandbox_v2: lossless data_schema reconstruction (fidelity #4) |
| 6 (appendix) | `f66e7e40344` | sandbox_v2: blanket ALWAYS_MAIN for ~18 helpers (fidelity appendix / point 1) |
| 7 (tracker/docs/STATUS) | _this commit_ | sandbox_v2: tick whats-changed + docs sweep + STATUS (fidelity batch close) |

## Per-item summary + test results

### #2 — CLI flag `--group` → `--name`
- Client `__main__.py`: arg renamed, help text updated, `SandboxRuntime(group=args.name)`.
- `manager._default_command` emits `"--name"`.
- Stub argv factories in `test_manager`/`test_phase9_shutdown`/`test_phase4_subprocess`
  (which launch the real module) + the parser test all updated.
- Tests: `tests/components/sandbox_v2/{test_manager,test_phase9_shutdown,test_phase4_subprocess}.py`
  + `hass_client/tests/test_sandbox_runtime.py` — **pass**.

### #7 — Reconstruct `vol.Invalid` instead of `TypeError`
- Both `channel.py` files: new `error_data_for()` serialises `vol.Invalid`
  (`{kind:invalid, msg, path}`) and `vol.MultipleInvalid`
  (`{kind:multiple, errors:[…]}`); path parts stringified. Error frame carries
  `error_data`; `_dispatch` threads it into `ChannelRemoteError(error_data=…)`.
- `bridge._translate_remote_error` rebuilds the real `vol.Invalid` /
  `vol.MultipleInvalid` (with `.path`) from `error_data`, falling back to the
  class-name mapping when absent.
- Tests: wire round-trip (`test_channel.py`, both invalid + multiple),
  `_translate_remote_error` rebuild + fallback (`test_bridge.py`), client wire
  round-trip (`test_sandbox_bridge.py`) — **pass**.

### #5 — Prefix proxy `unique_id` with source domain
- `UNIQUE_ID_SEPARATOR = ":"` documented in `const.py`.
- `_handle_register_entity` prefixes `unique_id` with `entry.domain`; `None`
  stays `None`.
- Test: two integrations reusing `"1"` land without collision with distinct
  `demo_a:1` / `demo_b:1` registry rows (`test_bridge.py`) — **pass**.

### #6 — Idempotent / updatable `register_entity`
- Client `EntityBridge` listens on `EVENT_ENTITY_REGISTRY_UPDATED` and
  `EVENT_DEVICE_REGISTRY_UPDATED`, re-describes + re-sends `MSG_REGISTER_ENTITY`
  for tracked entities, guarded by a hash of the description's mirrored fields
  (state-shaped keys excluded) to suppress event storms.
- Main `_handle_register_entity` upserts: existing proxy → `sandbox_update_description`
  (refreshes `_attr_*`, preserves the subclass's `IntFlag` supported_features
  type, re-runs the idempotent device `async_get_or_create`, writes state);
  else the create path.
- Tests: client entity-registry resend + hash-guard suppression, client
  device-registry resend (`test_entity_bridge.py`); main name-upsert (no
  duplicate) + device-firmware upsert (`test_bridge.py`) — **pass**.

### #4 — Lossless `data_schema` survival
- `reconstruct_schema` rebuilds real `selector.selector(entry["selector"])`
  and `data_entry_flow.section(reconstruct(...), {"collapsed": …})`; keeps
  string/int/float/bool/select; pass-through only for genuinely unknown shapes.
- Serialize-side `_has_data_schema` fallback now logs the dropped schema's repr
  at warning (`flow_runner.py`).
- Test: a schema with `SelectSelector` + `NumberSelector` inside a `section`
  round-trips serialize → reconstruct → re-serialize **equal** to the original
  (`test_phase14.py`) — **pass**.

### Appendix — blanket `ALWAYS_MAIN`
- Added broad readers (`template`, `group`, `homekit`) + 15 source-entity
  helpers to `ALWAYS_MAIN`, each with a one-line why.
- Verified `prometheus` + `alert` are `config_flow: false` (YAML-only) → already
  route to main, so **not** added (matches the plan).
- Test: dedicated parametrised `test_lockdown_helpers_pin_to_main` + the
  existing live-set parametrised test (`test_classifier.py`) — **pass**.

## Final test run
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` → **182 passed**.
- `uv run pytest sandbox_v2/hass_client/ -q` → **53 passed**.
- `uv run prek run --files <all touched files>` → clean (ruff/mypy/pylint/prettier/codespell).

## Doc updates (commit 7)
- `whats-changed.md`: ticked all 6 batch boxes with their commit SHAs.
- `OVERVIEW.md`: refreshed the entity-bridge section (upsert + registry-event
  resend, unique_id prefix), exception-translation section (vol.Invalid rebuild),
  and schema-reconstruction section (real selectors/sections); `--name` in the
  run-by-hand snippet + ASCII diagram.
- `README.md`, `architecture.html`: `--group` → `--name` in run snippets.
- Left historical records untouched: `STATUS-phase-*`, `plans/interview.md`,
  `plans/plan-v1-removal.md` (the Phase D instruction), `docs/FOLLOWUPS.md`.

## Anything weird
- The client device-registry resend test needs the entity registry loaded and a
  real device, which the minimal sandbox-private `FlowRunner` hass doesn't
  bootstrap. The test sets up `dr`/`er` explicitly, registers a config entry via
  the internal `_entries` collection, and creates a device — heavier than the
  other client tests but the only faithful way to exercise the device→entity
  lookup.
- The hash-guard test had a real ordering subtlety: the client's resend sets the
  description hash only *after* its `await channel.call(...)` returns, which is a
  tick after main records the call. The test settles a few event-loop ticks
  before firing the duplicate event so the guard is actually exercised.
- Did **not** touch `IGNORE_INTEGRATIONS_WITH_ERRORS`, did **not** start the
  `sandbox` rename, did **not** push — per the brief. Parent pushes.
