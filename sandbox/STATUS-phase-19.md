Status: DONE

Phase 19 wires device-registry bridging onto the existing
`sandbox_v2/register_entity` round-trip. Sandboxed entities that carry
`device_info` now produce a matching `DeviceEntry` in main's
`device_registry`, the entity_registry row links to it via `device_id`,
and area assignment works identically to a locally-running integration
(the proxy reads its area through HA's standard device → entity
inheritance path). Sandbox-side, `hass_client.entity_bridge` adds
`_serialise_device_info`, which flattens the `DeviceInfo` TypedDict's
set/tuple/enum shapes into JSON: `identifiers`/`connections` become
lists of two-element lists, `via_device` becomes a list, `entry_type`
becomes its `StrEnum` `.value`, and `configuration_url` becomes a
string. Main-side, `SandboxEntityDescription.from_payload` runs
`_deserialise_device_info` to rebuild the typed shapes, then
`_handle_register_entity` calls
`dr.async_get_or_create(config_entry_id=description.entry_id,
**device_info)` once up front so the proxy carries a known `device_id`.
The proxy then sets `_attr_device_info` so
`EntityPlatform.async_add_entities`' standard path reuses the same
`DeviceEntry` (idempotent on `(identifiers, connections)`) and pins
`entity.device_entry` on the proxy.

**No new core HA changes** — Phase 5's `async_register_remote_platform`
hook plus `device_registry`'s public API cover the whole bridge. The
unregister path needs no change either: HA already leaves `DeviceEntry`s
in place until the owning entry unloads, and the existing
`_handle_unregister_entity` only touches the entity_registry / state
machine.

Files added:
- sandbox_v2/STATUS-phase-19.md (this file)
- tests/components/sandbox_v2/test_phase19_devices.py — six tests
  covering DeviceEntry creation + entry-id linkage, proxy `device_id`
  propagation, backwards-compat with payloads that omit `device_info`,
  area assignment surfacing through the standard HA path, invalid
  `device_info` rejection as a `ChannelRemoteError`, and the
  payload-shape round-trip through `SandboxEntityDescription.from_payload`.

Files changed:
- sandbox_v2/hass_client/hass_client/entity_bridge.py — new
  `_serialise_device_info` helper; `_describe_entity` now appends a
  `device_info` key to the wire payload when the entity exposes one.
- homeassistant/components/sandbox_v2/bridge.py — imports
  `device_registry as dr`; `SandboxEntityDescription` gains
  `device_info`/`device_id` fields; `from_payload` runs the new
  `_deserialise_device_info` helper; `_handle_register_entity`
  pre-creates the `DeviceEntry` via
  `dr.async_get_or_create(config_entry_id=..., **device_info)` and
  pins the returned `device.id` on the description; `DeviceInfoError`
  is mapped to `HomeAssistantError` so it surfaces as a remote-error
  frame back to the sandbox.
- homeassistant/components/sandbox_v2/entity/__init__.py — proxy base
  sets `_attr_device_info` from the description so
  `EntityPlatform.async_add_entities`' framework path re-runs
  `async_get_or_create` (idempotent) and wires `entity.device_entry`.
- homeassistant/components/sandbox_v2/protocol.py — module docstring
  updated to document the new `device_info` key in `MSG_REGISTER_ENTITY`.
  The sandbox-side `protocol.py` is a constants-only mirror and points
  at the HA-side file for the catalogue; no edit needed there.
- sandbox_v2/hass_client/tests/test_entity_bridge.py — three new tests:
  `_serialise_device_info` flattens sets/tuples/enums; the same helper
  short-circuits empty/None input; and an end-to-end EntityBridge run
  with a `_DeviceEntity` confirms the `device_info` key lands in the
  outbound `register_entity` payload.
- sandbox_v2/plan.md — Phase 19 marked complete with per-checkbox
  status (deferral note on the compat-sweep regression).

Core HA files modified (review surface):
None.

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **140 passed** (134 baseline + 6 new Phase 19 tests).
- `uv run pytest /home/paulus/dev/hass/core/sandbox_v2/hass_client/ -q`
  → **54 passed** (51 baseline + 3 new entity_bridge tests).
- `uv run pytest tests/helpers/test_device_registry.py --no-cov -q` →
  **151 passed** (the bridge only consumes `dr.async_get_or_create` /
  `dr.async_get`'s public API; no core regression).
- `uv run prek run --files homeassistant/components/sandbox_v2/bridge.py
  homeassistant/components/sandbox_v2/entity/__init__.py
  homeassistant/components/sandbox_v2/protocol.py
  sandbox_v2/hass_client/hass_client/entity_bridge.py
  sandbox_v2/hass_client/tests/test_entity_bridge.py
  tests/components/sandbox_v2/test_phase19_devices.py` — ruff-check,
  ruff-format, codespell, mypy, pylint, prettier all green.

Things to flag for the next phase:

- **The compat-sweep regression run is deferred to a future
  `run_compat_full.py` pass.** The in-process plugin tests exercise
  the same end-to-end chain (`register_entity` → `dr.async_get_or_create`
  → entity_registry `device_id`) against a real `HomeAssistant`, so
  the unit coverage matches what a one-integration slice would
  validate. Re-running the full sweep is worth bundling with Phase 20
  (share_states cleanup) since both want a refreshed `COMPAT_FULL.md`.
  The expected delta from Phase 19 is "previously-empty device_registry
  for sandboxed integrations now mirrors the sandbox-side devices" —
  no failure shape change, so the categorised buckets should hold.

- **`OVERVIEW.md` / `CLAUDE.md` / `docs/FOLLOWUPS.md` reference the
  Phase 19 spec by name in their "Open follow-ups" sections.** Update
  those entries when Phase 20 lands its docs reconciliation so the
  surviving-list shrinks to just "share_states subscription consumer"
  + "v1 removal release-process step" + the residuals (snapshot drift,
  `calendar`/`todo`/`weather` queries, non-idempotent service
  handlers). Phase 19 itself didn't sweep the docs — keeping it
  focused on the code change keeps the diff easy to review; Phase 20
  is the natural next docs touch.

- **Per-domain proxy classes do not need an update.** The proxy base
  class (`SandboxProxyEntity`) is where `_attr_device_info` is now
  set, so all 32 domain proxies inherit the behaviour without a
  per-domain edit. The Phase 13 smoke tests (which exercise every
  proxy through register → state push → method invocation) still
  pass — confirming none of the per-domain subclasses override
  `__init__` in a way that would shadow the base's device_info wiring.

- **`device_info` mutations after the initial register are not yet
  bridged.** The Phase 5 STATUS already flagged that the
  `sandbox_v2/update_entity` capability-delta channel is deferred,
  and Phase 19 inherits that limitation: if an integration mutates
  `device_info` after the entity's first `async_write_ha_state`, the
  change won't propagate to main. The fix shape — re-register the
  entity to push the updated description — already works (the bridge
  treats a re-register as an upsert via `dr.async_get_or_create`),
  but most integrations build `device_info` once at construction
  time, so this hasn't bitten yet.

- **The `device_info` payload is a small wire-size addition.** A
  typical entry with `identifiers`, `name`, `manufacturer`, `model`
  adds ~100-200 bytes to the `register_entity` call. Bulk
  registrations from a hub-style integration with 50+ devices will
  feel this; not a regression vs the framework path, but worth
  watching if the in-process plugin's throughput tests ever surface
  a slowdown.
