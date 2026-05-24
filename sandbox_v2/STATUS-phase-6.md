Status: DONE

Phase 6 lands the sandbox→main service-registration mirror, event
mirror, and the approved-domains firewall they share. A single
refcounted `ApprovedDomains` instance is grown by `EntryRunner` when an
entry's `async_setup_entry` succeeds and by `EntityBridge` when an
entity registers, so the gate naturally tracks every domain the
sandbox actually owns. `ServiceMirror` listens on the sandbox bus for
`EVENT_SERVICE_REGISTERED` / `EVENT_SERVICE_REMOVED`, drops anything
the gate doesn't approve (with a warning log), and otherwise pushes
`sandbox_v2/register_service` (with `supports_response`) to main.
`SandboxBridge` on main installs a forwarder that ships each call back
over the existing `sandbox_v2/call_service` channel — never clobbering
an existing handler, so the `light.turn_on` registered by the host
`light` EntityComponent for Phase 5's proxy entities keeps its
dispatch role for entity services. `EventMirror` uses a `MATCH_ALL`
listener with an internal-events deny-list to forward only
`<approved_domain>_*` events via `sandbox_v2/fire_event`; main
re-fires each on its own bus so `automation` listeners react as if
the integration ran locally. **No core HA files were touched** — the
Phase 4 `router` hook and the Phase 5 `async_register_remote_platform`
hook are reused unchanged.

Files added:
- `sandbox_v2/hass_client/hass_client/approved_domains.py`
- `sandbox_v2/hass_client/hass_client/service_mirror.py`
- `sandbox_v2/hass_client/hass_client/event_mirror.py`
- `sandbox_v2/hass_client/tests/test_approved_domains.py`
- `sandbox_v2/hass_client/tests/test_service_mirror.py`
- `sandbox_v2/hass_client/tests/test_event_mirror.py`

Files changed:
- `sandbox_v2/hass_client/hass_client/protocol.py` — added
  `MSG_REGISTER_SERVICE`, `MSG_UNREGISTER_SERVICE`, `MSG_FIRE_EVENT`.
- `sandbox_v2/hass_client/hass_client/sandbox.py` — construct and
  register `ServiceMirror` + `EventMirror` alongside the existing
  `FlowRunner` / `EntryRunner` / `EntityBridge`; share a single
  `ApprovedDomains` instance; tear them down on shutdown.
- `sandbox_v2/hass_client/hass_client/entry_runner.py` — accept the
  shared `ApprovedDomains`; refcount-add the entry domain after
  `async_setup_entry` succeeds; refcount-remove on `entry_unload`.
- `sandbox_v2/hass_client/hass_client/entity_bridge.py` — accept the
  shared `ApprovedDomains`; refcount-add the entity's domain on each
  successful `register_entity` push (covers the *"light is approved
  if a sandboxed integration registers light entities"* clause).
- `homeassistant/components/sandbox_v2/protocol.py` — mirror the new
  message names.
- `homeassistant/components/sandbox_v2/bridge.py` — handle inbound
  `sandbox_v2/register_service` / `..._unregister_service` /
  `sandbox_v2/fire_event` on `SandboxBridge`; install a forwarder
  callable that translates each main-side service call into a
  `sandbox_v2/call_service` RPC (reusing Phase 5's exception
  translator); refuse to clobber an existing service handler.
- `tests/components/sandbox_v2/test_bridge.py` — add the four Phase 6
  bridge tests + a Phase-6 mock-domain ignore fixture.
- `sandbox_v2/plan.md` — Phase 6 section marked complete with summary
  and per-checkbox status (inline `*(...)*` notes for the few items
  the implementation simplified — e.g., schemas not serialised,
  manifest-dependencies clause supplanted by the entity-registration
  path).

Core HA files modified (review surface):
- None. (Phase 6 is purely sandbox-side glue plus integration-local
  handlers on main.)

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **56 passed** (52 from Phase 0–5 + 4 new bridge tests covering
  register / skip-existing / unregister / fire_event).
- `cd sandbox_v2/hass_client && uv run pytest -q` → **22 passed**
  (11 from Phase 0–5 + 5 `approved_domains` + 3 `service_mirror` +
  3 `event_mirror`).
- `uv run prek run --files <13 changed files>` → all hooks pass
  (ruff-check, ruff-format, codespell, mypy, pylint, prettier).

Things to flag for the next phase:

- **Service schemas are not serialised across the wire.** The Phase 6
  mirror registers `schema=None` on main and relies on the sandbox's
  copy of the schema to validate every call when it lands on the
  sandbox's `services.async_call`. This is fine for service handlers
  that re-validate or that are content with the raw `service_data`
  dict — but main's `voluptuous_serialize`-backed service-call UI
  cannot render argument hints for sandboxed services. The
  data_schema bridge already on the Phase 4/5 follow-up list should
  fold in service schemas at the same time.
- **`Context` is not faithfully forwarded.** `sandbox_v2/fire_event`
  carries the sandbox's `context_id` but main's `bus.async_fire`
  receives no `Context` object, so the event lands with a fresh
  local context. Listeners that key off `context.user_id` or
  `context.parent_id` won't see the sandbox-side values. Phase 7's
  auth scoping is the right place to revisit this — a sandbox token
  doesn't have user identity to forward anyway, and the design will
  need to settle what "origin sandbox" should look like in a
  `Context`.
- **Service-removal cleanup on unload depends on the sandbox's bus.**
  The bridge's `_mirrored_services` set tracks what *the bridge
  installed*, so an entry unload that runs `services.async_remove`
  inside the sandbox triggers `EVENT_SERVICE_REMOVED` →
  `sandbox_v2/unregister_service` → main drop. Integrations that
  bypass `services.async_remove` on unload (rare but legal) will
  leave a dangling forwarder on main. Phase 9's graceful-shutdown
  pass should iterate `_mirrored_services` and drop the lot on
  sandbox process exit as a backstop.
- **`MATCH_ALL` event listener cost.** `EventMirror` subscribes to
  every event on the sandbox bus and does a per-event prefix scan
  against the approved-domain set. This is cheap (one O(domains)
  scan per event, short-circuit on the deny-list) but worth a
  second look once Phase 10's compat lane lets us measure event
  throughput under load. If it shows up, swapping to a
  domain-indexed subscription map (one listener per
  `<domain>_*` prefix, re-bound when the set grows) avoids the
  per-event scan.
- **No cross-context entry-unload service cleanup yet.** When the
  router calls `bridge.async_unload_entry(entry)`, the bridge drops
  the entity platforms for that entry but does not yet
  cross-reference which mirrored services belonged to the entry
  (the sandbox doesn't tell us). If the integration's
  `async_unload_entry` doesn't unregister its services on the
  sandbox side, those forwarders stick around until the sandbox
  process exits. Pair this fix with the dangling-forwarder backstop
  above when Phase 9 lands.
- **Approved-domains check is a one-way ratchet today.** `EntryRunner`
  removes one refcount on `entry_unload` and `EntityBridge` doesn't
  decrement on entity unregister at all — so once a domain has been
  approved by an entity, it stays approved for the lifetime of the
  sandbox process. That's fine while we're additive but means a
  sandbox that briefly hosted a `light` keeps light approved even
  after every light is gone. Tightening this needs the
  `EntityBridge` to refcount on `_push_unregister` too; not urgent
  for v2 but worth noting for the hardening pass.
