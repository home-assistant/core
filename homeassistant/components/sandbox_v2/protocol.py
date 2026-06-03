"""Phase 5 wire-protocol constants and payload helpers.

The integration and the sandbox runtime exchange JSON-line messages over
the :class:`Channel` set up in Phase 4. Each message type is namespaced
``sandbox_v2/…``. Both sides share the same names — kept here on the HA
side and mirrored verbatim in :mod:`hass_client.protocol` so neither has
to import the other.

Main → Sandbox calls:

* ``sandbox_v2/entry_setup``  — push a serialised :class:`ConfigEntry` into
  the sandbox, asking it to load the owning integration and run
  ``async_setup_entry``. Returns ``{"ok": bool, "reason": str | None}``.
* ``sandbox_v2/entry_unload`` — ask the sandbox to unload an entry by id.
* ``sandbox_v2/call_service``  — generic service dispatch (shared with
  Phase 6's main→sandbox service mirroring path). Payload mirrors a
  ``ServiceCall``: ``(domain, service, target, service_data, context,
  return_response)``. Returns either ``None`` or a service-response dict.

Sandbox → Main calls:

* ``sandbox_v2/register_entity`` — sandbox tells main "I just added an
  entity, here's its description". Main builds the proxy and replies
  ``{"entity_id": <main-side id>}`` so the sandbox can route later
  ``call_service`` requests back to the right local entity. Optional
  ``device_info`` field (Phase 19): a JSON-flattened ``DeviceInfo`` dict
  — sets become lists of two-element lists (``identifiers`` /
  ``connections``), tuples become lists (``via_device``), and
  ``entry_type`` is the enum's string value. When present, main calls
  :func:`device_registry.async_get_or_create` so the sandbox's devices
  surface in main's device_registry tied to the sandboxed entry.
* ``sandbox_v2/unregister_entity`` — symmetric counterpart.
* ``sandbox_v2/state_changed``   — push (no response). Carries the
  marshalled state delta for one entity.
* ``sandbox_v2/register_service`` (Phase 6) — sandbox tells main "I just
  registered a service, please mirror it". Main installs a thin handler
  that forwards calls back over the shared ``sandbox_v2/call_service``
  channel.
* ``sandbox_v2/unregister_service`` (Phase 6) — symmetric counterpart.
* ``sandbox_v2/fire_event`` (Phase 6) — push (no response). The sandbox
  forwards each ``<owned_domain>_*`` event so main listeners (notably
  ``automation``) can react as if the integration ran locally.
* ``sandbox_v2/store_load`` (Phase 8) — sandbox-side ``Store.async_load``
  proxies to this RPC. Payload ``{"key": str}``; response is the wrapped
  ``{"version", "minor_version", "key", "data"}`` dict the sandbox last
  saved, or ``None`` if no data exists yet. The group is implicit from
  the channel — each :class:`SandboxBridge` only ever serves one group.
* ``sandbox_v2/store_save`` (Phase 8) — sandbox-side ``Store`` flush.
  Payload ``{"key": str, "data": dict}``; main writes the wrapped dict
  to ``<config>/.storage/sandbox_v2/<group>/<key>`` atomically. Response
  is ``{"ok": True}``.
* ``sandbox_v2/store_remove`` (Phase 8) — sandbox-side
  ``Store.async_remove``. Payload ``{"key": str}``; main unlinks the
  file (if any). Response is ``{"ok": True}``.

Main → Sandbox shutdown (Phase 9):

* ``sandbox_v2/shutdown`` — ask the runtime to unload its entries, dump
  ``RestoreEntity`` state, fire ``EVENT_HOMEASSISTANT_FINAL_WRITE`` so any
  pending Stores flush to main via the ``current_sandbox`` store bridge,
  and exit cleanly. Response ``{"ok": True, "unloaded": int, "restored":
  int}``. The runtime sets its shutdown event right after writing the
  reply, so the subprocess exits 0 on its own — main only needs SIGTERM
  if the round-trip times out.
"""

from typing import Final

# Main → Sandbox
MSG_ENTRY_SETUP: Final = "sandbox_v2/entry_setup"
MSG_ENTRY_UNLOAD: Final = "sandbox_v2/entry_unload"
MSG_CALL_SERVICE: Final = "sandbox_v2/call_service"
MSG_SHUTDOWN: Final = "sandbox_v2/shutdown"

# Sandbox → Main
MSG_REGISTER_ENTITY: Final = "sandbox_v2/register_entity"
MSG_UNREGISTER_ENTITY: Final = "sandbox_v2/unregister_entity"
MSG_STATE_CHANGED: Final = "sandbox_v2/state_changed"
MSG_REGISTER_SERVICE: Final = "sandbox_v2/register_service"
MSG_UNREGISTER_SERVICE: Final = "sandbox_v2/unregister_service"
MSG_FIRE_EVENT: Final = "sandbox_v2/fire_event"
MSG_STORE_LOAD: Final = "sandbox_v2/store_load"
MSG_STORE_SAVE: Final = "sandbox_v2/store_save"
MSG_STORE_REMOVE: Final = "sandbox_v2/store_remove"


__all__ = [
    "MSG_CALL_SERVICE",
    "MSG_ENTRY_SETUP",
    "MSG_ENTRY_UNLOAD",
    "MSG_FIRE_EVENT",
    "MSG_REGISTER_ENTITY",
    "MSG_REGISTER_SERVICE",
    "MSG_SHUTDOWN",
    "MSG_STATE_CHANGED",
    "MSG_STORE_LOAD",
    "MSG_STORE_REMOVE",
    "MSG_STORE_SAVE",
    "MSG_UNREGISTER_ENTITY",
    "MSG_UNREGISTER_SERVICE",
]
