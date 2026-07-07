# Home Assistant Sandbox

This directory is the home for the sandbox rewrite (renamed from its earlier
`_v2` suffix once v1 was gone). The sandbox runs Home Assistant integrations in
isolated subprocesses while main keeps a single unified view of devices,
entities, services, and events.

v1 has been **removed** (2026-05-28) — it previously occupied these same
paths (`../sandbox/` and `../homeassistant/components/sandbox/`) that the
rewrite now lives at; recover it from git history if ever needed. This
happened before the rewrite shipped a stable release (the documented gate's
second condition), as a deliberate call relying on git history for rollback.

## Read these first

- [`OVERVIEW.md`](OVERVIEW.md) — full architecture: routing,
  lifecycle, flow forwarding, entity bridge, service/event mirror,
  scoped auth, store routing, shutdown, test infra.
- [`plan.md`](plan.md) — phase-by-phase task list. Phases 0–20 are
  all ✅ COMPLETE; the follow-up phases (12 concurrent dispatcher,
  13 remaining domain proxies, 14 schema/unique_id/unload-hook/perf,
  15 v1-baseline sweep, 16 cross-integration sweep + backlog,
  17 `ConfigEntry.sandbox` field, 19 device-registry bridging,
  20 drop unwired `share_*` + design doc) closed every Phase 5–10
  deferral; the state-sharing consumer is now an explicit design
  ([`docs/design-share-states.md`](docs/design-share-states.md))
  rather than dead-flag carrying. See
  [`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md) for the narrative.
- [`STATUS-phase-N.md`](.) — the authoritative landing notes for each
  phase. **Always check the latest STATUS file before assuming
  something is wired up the way the plan describes** — phases
  deliberately defer or simplify items and note exactly what
  changed.
- [`docs/entity-bridge-decision.md`](docs/entity-bridge-decision.md) —
  Option A vs Option B (Phase 1 spike). Option B (action-call
  forwarding via the shared `sandbox/call_service` channel) is
  the protocol every entity proxy uses.
- [`docs/auth-scoping-decision.md`](docs/auth-scoping-decision.md) —
  **SUPERSEDED.** The Phase-7 `RefreshToken.scopes` mechanism it
  describes was reverted from core HA (`plans/plan-strip-auth-scopes.md`),
  and `plans/plan-auth-context.md` then dropped the sandbox token + the
  per-group system user entirely — the sandbox now holds **no** credential.
  Kept as the design record for whenever the sandbox→main websocket
  actually lands (the credential is redesigned fresh then).
- [`docs/design-share-states.md`](docs/design-share-states.md) —
  design for the post-v2 state-sharing consumer that replaces the
  Phase 7 `share_*` flags Phase 20 deleted. Covers entity_id
  alignment, the `share/subscribe_*` protocol, main-side filtering,
  and the open questions.

## Repository layout

- `hass_client/` — Python client library (its own `uv` env). Hosts
  `SandboxRuntime`, `FlowRunner`, `EntryRunner`, `EntityBridge`,
  `ServiceMirror`, `EventMirror`, `ChannelSandboxBridge`, and the two
  pytest plugins under `hass_client/testing/`. Also carries the runtime's
  **Docker test image** (`hass_client/Dockerfile` + `docker-compose.test.yml`)
  — see [`hass_client/docs/docker.md`](hass_client/docs/docker.md).
- `docs/` — per-phase decision write-ups.
- `run_compat.py` + `COMPAT.md` + `COMPAT.csv` — compat-lane runner
  and report (Phase 10).

The HA Core side of the integration lives at
`../homeassistant/components/sandbox/`.

## Stateless sandboxes — integration source

Sandboxes hold no persistent state: config is pushed on `entry_setup`,
storage/restore-state routes to main via the `current_sandbox` store bridge,
and the **last stateful bit — the integration code — is now fetched at
startup**. `EntrySetup.integration_source` (a typed proto sub-message) tells
the sandbox where to get the code:

- Built-in → `{kind: "builtin"}`, a no-op (the bundled `homeassistant`
  package provides it).
- Custom (HACS) → `{kind: "git", url, ref, tag, domain, subdir}`; the sandbox
  downloads the codeload tarball for the exact `ref` (commit sha) into
  `<config>/custom_components/<domain>` before `async_setup`.

**Resolver-hook contract.** Core stays HACS-agnostic. `sources.py` (HA side)
exposes `async_register_sandbox_source_resolver(hass, resolver)`; a resolver
maps a custom `domain → IntegrationSource-dict | None`. Built-ins
short-circuit (`Integration.is_built_in`) without consulting a resolver; a
custom domain with no resolver **raises** rather than silently falling back.
The resolver MUST pin `ref` to an exact commit sha — core performs **no
network I/O**, so it trusts the resolver's pin (`tag` is logs-only). The fetch
+ process-lifetime `(url, ref)` cache live in `hass_client/sources.py`; the
download primitive is injectable so tests never hit the network. See
OVERVIEW.md "Integration source — fetch before setup (stateless)".

Runtime gap (follow-up, pairs with `plan-docker.md`): the bare-HA sandbox must
run `async_process_requirements` (pip) for custom integrations that ship
Python deps, and needs network egress (GitHub + PyPI). The wire + fetch are
shipped + tested; the pip/egress runtime is not validated here.

## Core HA files modified (high-review surface)

v2 touches three core HA surfaces. Each is intentional, small, and was
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
- `homeassistant/helpers/sandbox_context.py` (NEW) +
  `homeassistant/helpers/storage.py` — the `current_sandbox`
  `ContextVar` + `SandboxBridge` `Protocol`, read by `Store`'s IO
  methods (`_async_load_data`, `_async_write_data`, `async_remove`) so
  sandbox `Store` IO routes to main at call time. This **replaced** the
  Phase 8 module-level `Store` rebinding — no more monkey-patch.
  **plan-sandbox-context (Phase A1 + A2).**

Iron Law: do **not** monkey-patch private internals. v1's direct
write to `EntityComponent._platforms` is the cautionary tale —
v2 took the slightly bigger PR to add the public hook instead. The
Phase 8 `Store` rebinding was the same smell; plan-sandbox-context
replaced it with the declared `current_sandbox` core HA hook.

## Open follow-ups (not yet shipped)

The Phase 5–10 list of deferred items is mostly closed. See
[`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md) for the narrative chain that
took the codebase from Phase 11 to Phase 17. What's still open:

- **State-sharing subscription consumer + main-side filtering.**
  Phase 20 deleted the unwired `SharingConfig` /
  `SandboxGroupConfig` surface and replaced it with a design
  ([`docs/design-share-states.md`](docs/design-share-states.md))
  covering the entity_id alignment constraint, the
  `share/subscribe_*` protocol, the main-side filter, and the
  remaining open questions. The actual consumer + main-side
  handlers are owed in a future phase against that design.
- **v1 removal. DONE (2026-05-28).** The numeric gate (Phase 11) was cleared
  by Phase 17 (99.67 % full sweep, 99.97 % v1 baseline). v1 (`../sandbox/` +
  `../homeassistant/components/sandbox/` + `tests/components/sandbox/`) was
  removed ahead of the "v2 shipped a stable release" condition, relying on git
  history for rollback.
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
- **Cross-sandbox in-process dependencies (ESPHome serial / BLE
  proxy).** Some integration pairs are coupled in-process — e.g. an
  ESPHome device acting as a serial proxy that another integration
  (ZHA, zwave_js, deCONZ, …) connects to. Today this only works if
  both integrations land in the *same* sandbox group, because the
  setup-time coordination (proxy enumeration, port lookup) happens
  via Python calls/events that the bridge doesn't cross. The classifier
  routes by built-in / custom / system, so a built-in ESPHome + custom
  consumer would split across sandboxes and break. The fix shape is
  either (a) a "co-locate with X" hint that overrides classifier
  output for known coupled pairs, or (b) routing the coordination
  events through the service/event mirror Phase 6 built — currently
  the mirror only forwards events whose name starts with
  `<owned_domain>_`, which catches `esphome_*` but not the consuming
  side's discovery hooks. BLE proxy has the same shape. IR / RF (e.g.
  Broadlink) are simpler — they're one-way command flows, so a
  consumer just needs to *send* commands; no setup-time enumeration
  or bidirectional stream — but still need dedicated cross-sandbox
  support since the consumer's send-call has to reach the producer.
  Worth a small spec before any cross-sandbox split actually trips
  this.

## Tests

```bash
# HA-core side
uv run pytest tests/components/sandbox/ --no-cov -q

# Client side (separate uv env — does NOT accept --no-cov)
uv run pytest /home/paulus/dev/hass/core/sandbox/hass_client/ -q

# Compat lane
cd sandbox && python run_compat.py
```

For running the client runtime in a container (unix-socket transport today, WS
later — not remote-ready yet), see
[`hass_client/docs/docker.md`](hass_client/docs/docker.md).

After modifying anything under `sandbox/` or
`homeassistant/components/sandbox/`, run
`uv run prek run --files <changed files>` before committing.
