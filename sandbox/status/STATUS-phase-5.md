Status: DONE

Phase 5 wires the entity bridge end-to-end. The sandbox runtime now
hosts an `EntryRunner` that rebuilds a `ConfigEntry` from the
`sandbox_v2/entry_setup` payload, drops it into the sandbox's
`ConfigEntries`, and runs the integration's `async_setup_entry` against
the sandbox-private `HomeAssistant`. The sandbox's `EntityBridge`
listens for `EVENT_STATE_CHANGED` and pushes `sandbox_v2/register_entity`
(first appearance) and `sandbox_v2/state_changed` (subsequent updates)
to main. On main, `SandboxBridge` instantiates a domain-specific proxy
entity from `homeassistant/components/sandbox_v2/entity/` and attaches
it to the matching `EntityComponent` via the new
`EntityComponent.async_register_remote_platform` core hook. Proxy
service methods (e.g., `light.async_turn_on`) translate into
`sandbox_v2/call_service` RPCs via a per-loop-tick batcher that
coalesces matching `(domain, service, service_data)` calls into one
multi-entity RPC. An exception translator maps `vol.Invalid` from the
sandbox's schema layer back to `TypeError` so callers see the
local-entity error shape. Phase 4's LOADED stub is replaced — the
router now actually awaits the round-trip and surfaces `SETUP_ERROR` or
`SETUP_RETRY` on failure.

Files added:
- `homeassistant/components/sandbox_v2/bridge.py`
- `homeassistant/components/sandbox_v2/entity/__init__.py`
- `homeassistant/components/sandbox_v2/entity/binary_sensor.py`
- `homeassistant/components/sandbox_v2/entity/light.py`
- `homeassistant/components/sandbox_v2/entity/sensor.py`
- `homeassistant/components/sandbox_v2/entity/switch.py`
- `homeassistant/components/sandbox_v2/protocol.py`
- `sandbox_v2/hass_client/hass_client/entity_bridge.py`
- `sandbox_v2/hass_client/hass_client/entry_runner.py`
- `sandbox_v2/hass_client/hass_client/protocol.py`
- `sandbox_v2/hass_client/tests/test_entity_bridge.py`
- `sandbox_v2/hass_client/tests/test_entry_runner.py`
- `tests/components/sandbox_v2/test_bridge.py`

Files changed:
- `homeassistant/components/sandbox_v2/__init__.py` — wire one
  `SandboxBridge` per group via the manager's `on_channel_ready`
  callback; expose `SandboxV2Data.bridges`.
- `homeassistant/components/sandbox_v2/router.py` — replace the
  Phase-4 LOADED stub with a real `sandbox_v2/entry_setup` round-trip;
  add an `async_unload_entry` helper for future use; surface
  `SETUP_ERROR` / `SETUP_RETRY` on refusal.
- `sandbox_v2/hass_client/hass_client/sandbox.py` — construct and
  register the `EntryRunner` and `EntityBridge` alongside the
  Phase-4 `FlowRunner`; tear the bridge down on shutdown.
- `tests/components/sandbox_v2/test_init.py` — assert the new
  `bridges` dict on `SandboxV2Data`.
- `tests/components/sandbox_v2/test_router.py` — drive the new
  channel round-trip in `async_setup_entry` via a stub responder; add
  a `SETUP_ERROR`-on-refusal test.
- `tests/components/sandbox_v2/test_proxy_flow.py` — extend the
  flow stub with `entry_setup` / `entry_unload` handlers so the full
  flow's setup interception completes.
- `sandbox_v2/plan.md` — Phase 5 section marked complete with
  per-checkbox status (inline `*(Deferred …)*` notes for the 28
  remaining proxies, capability deltas, and the websocket-perf check
  that lives with Phase 10's compat lane).

Core HA files modified (review surface):
- `homeassistant/helpers/entity_component.py:207-225` — new
  `EntityComponent.async_register_remote_platform(config_entry,
  platform)`. Mirrors `async_setup_entry`'s `_platforms[entry_id] =
  platform` assignment but lets sandbox_v2 hand in a pre-built remote
  `EntityPlatform` (rather than discovering one from the local
  integration). 1 new method, 0 changes to existing paths. Phase 5
  notes: this is the only Phase-5 core change; the Phase-4
  `router` hook is reused unchanged.

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **52 passed** (44 from Phase 0–4 + 8 new bridge tests).
- `cd sandbox_v2/hass_client && uv run pytest -q` → **11 passed**
  (7 from Phase 0–4 + 1 new entity_bridge test + 3 new entry_runner
  tests).
- `uv run pytest tests/test_config_entries.py tests/helpers/test_entity_component.py --no-cov -q`
  → **413 passed, 4 snapshots passed** — the new EntityComponent
  hook is benign when not used.
- `uv run prek run --files <21 changed files>` → all hooks pass
  (ruff-check, ruff-format, codespell, mypy, pylint, prettier).

Things to flag for the next phase:

- **28 of 32 domain proxies are still placeholders.** Phase 5 ships
  proxies for `light`, `switch`, `sensor`, `binary_sensor` to prove
  the path. Unknown-domain registrations fall back to the generic
  `SandboxProxyEntity` which has no domain-typed properties, so a
  sandboxed `climate` entity (for example) currently registers but
  reports no `hvac_mode`, `target_temperature`, etc. The base class
  + `_DOMAIN_PROXIES` map are designed so each new proxy is a
  drop-in 20–80 LOC file (compare with v1's
  `homeassistant/components/sandbox/entity/`). Phase 5b.
- **Capability delta protocol stub.** The plan called for a
  `sandbox_v2/update_entity` message for capability mutations after
  registration; Phase 5 surfaces capabilities only at register time
  and relies on re-registration for changes. Most integrations don't
  mutate capabilities post-setup, so this hasn't bitten yet — but
  `climate` and `cover` are known offenders.
- **`async_unload_entry` core call site.** Router has
  `async_unload_entry` ready to wire (pushes `entry_unload` over the
  channel and calls `bridge.async_unload_entry`), but
  `homeassistant.config_entries.async_unload` does not consult the
  router. Adding the third call site means amending
  `ConfigEntryRouter` Protocol and `ConfigEntries.async_unload` —
  worth a Phase 5b PR since the integration code on main never
  loaded, so calling `entry.async_unload(hass)` blows up trying to
  invoke `async_unload_entry` on a module that has no integration
  state.
- **`data_schema` is still stripped on the flow wire.** Phase 4's
  STATUS flagged this; Phase 5 didn't tackle it. Frontend forms for
  sandboxed integrations still won't render correctly. The
  `voluptuous_serialize`-based bridge is its own piece of work.
- **`unique_id` propagation through the proxy flow.** Phase 4's
  STATUS flagged this; Phase 5 didn't tackle it. A sandboxed flow
  that calls `self.async_set_unique_id(...)` doesn't reflect that
  back to main's flow.context. Same shape as the data_schema
  follow-up — a small marshalling extension to `_marshal_result`.
- **Performance benchmark deferred.** The 200-light area call under
  ~50 ms target is an end-to-end-over-websocket measurement; the
  in-process channel pair the bridge tests use measures something
  different. Hook up with Phase 10's compat lane.
- **`config_entries.async_unload`'s component-not-loaded path is
  fragile for sandboxed entries.** Even without an
  `async_unload_entry` Protocol method, the entry's state is
  `LOADED` after Phase 5 sets up successfully, so HA will try to
  unload via the local `component.async_unload_entry` on
  `entry.async_unload(hass)`. The integration module loads on main
  (manifest discovery) but `async_setup_entry` was never called on
  main, so its `hass.data` slot is missing and most integrations'
  unload functions raise `KeyError`. Phase 6 should land the
  unload-route hook before any UI-driven removal path is exercised.
- **Auto-loading of host domains on first register.** The bridge
  calls `async_setup_component(domain)` on the first `register_entity`
  for an unfamiliar domain. This loads the platform module on main
  (`light`, `switch`, …) which is correct, but it does so lazily,
  meaning a brief delay on the very first entity of each domain. If
  this matters for perception, the manager could pre-load the
  domains declared by an integration's `manifest.json` at
  `entry_setup` time.
- **`SandboxLightEntity.__init__` re-wraps `supported_features` in
  `LightEntityFeature`.** The base proxy stores an `int`, but the
  light's `capability_attributes` does `X in supported_features`,
  which only works on the IntFlag. Other domains that index
  `supported_features` with `in` (`fan`, `cover`, …) will need the
  same per-class wrapping when their proxies land.
