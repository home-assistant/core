# Home Assistant Sandbox v2

This directory is the home for the v2 sandbox rewrite. v2 runs Home
Assistant integrations in isolated subprocesses while main keeps a
single unified view of devices, entities, services, and events.

v1 still lives at `../sandbox/` and `../homeassistant/components/sandbox/`
and is kept for reference until v2 has matched v1's compat numbers
and shipped at least one stable release. **Do not delete or modify
v1** while working in this directory.

## Read these first

- [`OVERVIEW.md`](OVERVIEW.md) — full architecture: routing,
  lifecycle, flow forwarding, entity bridge, service/event mirror,
  scoped auth, store routing, shutdown, test infra.
- [`plan.md`](plan.md) — phase-by-phase task list. Phases 0–17 are
  all ✅ COMPLETE; the follow-up phases (12 concurrent dispatcher,
  13 remaining domain proxies, 14 schema/unique_id/unload-hook/perf,
  15 v1-baseline sweep, 16 cross-integration sweep + backlog,
  17 `ConfigEntry.sandbox` field) closed every Phase 5–10 deferral
  except the `share_states=True` subscription consumer. See
  [`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md) for the narrative.
- [`STATUS-phase-N.md`](.) — the authoritative landing notes for each
  phase. **Always check the latest STATUS file before assuming
  something is wired up the way the plan describes** — phases
  deliberately defer or simplify items and note exactly what
  changed.
- [`docs/entity-bridge-decision.md`](docs/entity-bridge-decision.md) —
  Option A vs Option B (Phase 1 spike). Option B (action-call
  forwarding via the shared `sandbox_v2/call_service` channel) is
  the protocol every entity proxy uses.
- [`docs/auth-scoping-decision.md`](docs/auth-scoping-decision.md) —
  why `scopes` lives on `RefreshToken` itself, the
  `_scope_allows` grammar, and what's deferred until the sandbox
  websocket back to main is wired up.

## Repository layout

- `hass_client/` — Python client library (its own `uv` env). Hosts
  `SandboxRuntime`, `FlowRunner`, `EntryRunner`, `EntityBridge`,
  `ServiceMirror`, `EventMirror`, `RemoteStore`, and the two pytest
  plugins under `hass_client/testing/`.
- `docs/` — per-phase decision write-ups.
- `run_compat.py` + `COMPAT.md` + `COMPAT.csv` — compat-lane runner
  and report (Phase 10).

The HA Core side of the integration lives at
`../homeassistant/components/sandbox_v2/`.

## Core HA files modified (high-review surface)

v2 touches three core HA files. Each is intentional, small, and was
introduced by a specific phase — see the matching STATUS file for
the rationale.

- `homeassistant/config_entries.py` — three additions on the same
  `router` attribute, plus the `ConfigEntry.sandbox` field that
  carries the routing tag without polluting `entry.data`.
  - `ConfigEntries.router` attribute + `ConfigEntryRouter` `Protocol`,
    consulted from `ConfigEntriesFlowManager.async_create_flow` and
    `ConfigEntries.async_setup`. **Phase 4.**
  - `ConfigEntries.async_unload` consults `router.async_unload_entry`
    before falling through to `entry.async_unload(hass)`. **Phase 14.**
  - `ConfigEntry.sandbox: str | None` field (declaration + `__init__`
    kwarg + `as_dict` write + storage read + `ConfigFlowResult["sandbox"]`
    plumbed through `async_finish_flow`). **Phase 17.**
- `homeassistant/helpers/entity_component.py` —
  `EntityComponent.async_register_remote_platform`. Sandbox-built
  `EntityPlatform` instances attach without re-discovering the
  local integration. **Phase 5.**
- `homeassistant/auth/models.py` + `auth/__init__.py` +
  `auth/auth_store.py` + `components/websocket_api/connection.py` —
  optional `RefreshToken.scopes` + dispatcher enforcement. **Phase 7.**

Iron Law: do **not** monkey-patch private internals. v1's direct
write to `EntityComponent._platforms` is the cautionary tale —
v2 took the slightly bigger PR to add the public hook instead.

## Open follow-ups (not yet shipped)

The Phase 5–10 list of deferred items is mostly closed. See
[`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md) for the narrative chain that
took the codebase from Phase 11 to Phase 17. What's still open:

- **`share_states=True` subscription consumer + main-side
  filtering.** The config knob is wired; the consumer that opens a
  subscription back to main and the filtering on main's emit path
  are owed in the same PR.
- **v1 removal.** The numeric gate (Phase 11) is **now satisfied** —
  Phase 17 cleared the 99.5 % v1-removal threshold (99.67 % full
  sweep, 99.97 % v1 baseline). The remaining condition is "v2 has
  shipped at least one stable release," which is a release-process
  step rather than a code change. Keep `sandbox/` and
  `homeassistant/components/sandbox/` around until that ships, then
  queue v1 removal for the release after.
- **Diagnostic snapshot drift / clock-pinning.** Phase 17's
  `BACKLOG.md` documents two test-side residuals: ~30 diagnostic
  snapshots showing `+ 'sandbox': 'built-in'` (fix is `pytest
  --snapshot-update` per integration) and ~70 `created_at` snapshot
  drifts (fix is integration-side freezegun, or an optional Phase
  17b clock-pinning fixture on the compat plugin — ~30 LOC).
- **`calendar` / `todo` / `weather` query-shaped RPCs.** The Phase
  13 proxies return empty lists for `async_get_events`, `todo_items`,
  and `weather.async_forecast_*` because the action-call channel
  can't express server-side queries. Add a query-shaped RPC if the
  compat sweep ever surfaces an integration that needs them.
- **Non-idempotent service handlers** (`ai_task`, `image`).
  `ALWAYS_MAIN` punt for v2; v3 spec on service-handler-level
  interception or sandbox-aware integration hooks is the long-term
  fix. See the Phase 1 spike doc.

## Tests

```bash
# HA-core side
uv run pytest tests/components/sandbox_v2/ --no-cov -q

# Client side (separate uv env — does NOT accept --no-cov)
uv run pytest /home/paulus/dev/hass/core/sandbox_v2/hass_client/ -q

# Compat lane
cd sandbox_v2 && python run_compat.py
```

After modifying anything under `sandbox_v2/` or
`homeassistant/components/sandbox_v2/`, run
`uv run prek run --files <changed files>` before committing.
