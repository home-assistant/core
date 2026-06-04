"""Wire-protocol message-type constants.

The integration and the sandbox runtime exchange typed protobuf messages
over the :class:`Channel`. Each message type is namespaced ``sandbox/…``;
this module holds the type-string constants. Both sides share the same
names — kept here on the HA side and mirrored verbatim in
:mod:`hass_client.protocol` so neither has to import the other.

The wire is protobuf (default codec :class:`~.codec_protobuf.ProtobufCodec`):
each ``type`` maps to a request/result proto message pair in
:mod:`.messages` (the `REGISTRY`), generated from
``sandbox/proto/sandbox.proto``. The payload shapes described below
are the *logical* contract for each call — they are carried as those typed
proto messages, not free-form dicts (only genuinely dynamic fields, e.g.
``service_data`` / state attributes / serialized voluptuous schemas, cross
as ``Struct`` / ``ListValue``). The line-oriented :class:`~.channel.JsonCodec`
is retained only as the channel-core test/debug wire.

Main → Sandbox calls:

* ``sandbox/entry_setup``  — push a serialised :class:`ConfigEntry` into
  the sandbox, asking it to load the owning integration and run
  ``async_setup_entry``. Returns ``{"ok": bool, "reason": str | None}``.
  Carries an ``integration_source`` sub-message telling a stateless sandbox
  where to fetch the integration code: ``{kind: "builtin"}`` (the bundled
  ``homeassistant`` package provides it — a no-op) or ``{kind: "git", url,
  ref, tag, domain, subdir}`` for custom (HACS) integrations. ``ref`` is an
  exact commit sha (main pins tag→sha; see ``sources.py``); the sandbox
  fetches the code before setup (see ``hass_client.sources``).
* ``sandbox/entry_unload`` — ask the sandbox to unload an entry by id.
* ``sandbox/call_service``  — generic service dispatch (shared with
  the main→sandbox service mirroring path). Payload mirrors a
  ``ServiceCall``: ``(domain, service, target, service_data, context,
  return_response)``. Returns either ``None`` or a service-response dict.

Sandbox → Main calls:

* ``sandbox/register_entity`` — sandbox tells main "I just added an
  entity, here's its description". Main builds the proxy and replies
  ``{"entity_id": <main-side id>}`` so the sandbox can route later
  ``call_service`` requests back to the right local entity. Optional
  ``device_info`` field: a JSON-flattened ``DeviceInfo`` dict
  — sets become lists of two-element lists (``identifiers`` /
  ``connections``), tuples become lists (``via_device``), and
  ``entry_type`` is the enum's string value. When present, main calls
  :func:`device_registry.async_get_or_create` so the sandbox's devices
  surface in main's device_registry tied to the sandboxed entry.
* ``sandbox/unregister_entity`` — symmetric counterpart.
* ``sandbox/state_changed``   — push (no response). Carries the
  marshalled state delta for one entity.
* ``sandbox/register_service`` — sandbox tells main "I just
  registered a service, please mirror it". Main installs a thin handler
  that forwards calls back over the shared ``sandbox/call_service``
  channel.
* ``sandbox/unregister_service`` — symmetric counterpart.
* ``sandbox/fire_event`` — push (no response). The sandbox
  forwards each ``<owned_domain>_*`` event so main listeners (notably
  ``automation``) can react as if the integration ran locally.
* ``sandbox/store_load`` — sandbox-side ``Store.async_load``
  proxies to this RPC. Payload ``{"key": str}``; response is the wrapped
  ``{"version", "minor_version", "key", "data"}`` dict the sandbox last
  saved, or ``None`` if no data exists yet. The group is implicit from
  the channel — each :class:`SandboxBridge` only ever serves one group.
* ``sandbox/store_save`` — sandbox-side ``Store`` flush.
  Payload ``{"key": str, "data": dict}``; main writes the wrapped dict
  to ``<config>/.storage/sandbox/<group>/<key>`` atomically. Response
  is ``{"ok": True}``.
* ``sandbox/store_remove`` — sandbox-side
  ``Store.async_remove``. Payload ``{"key": str}``; main unlinks the
  file (if any). Response is ``{"ok": True}``.

Main → Sandbox shutdown:

* ``sandbox/shutdown`` — ask the runtime to unload its entries, dump
  ``RestoreEntity`` state, fire ``EVENT_HOMEASSISTANT_FINAL_WRITE`` so any
  pending Stores flush to main via the ``current_sandbox`` store bridge,
  and exit cleanly. Response ``{"ok": True, "unloaded": int, "restored":
  int}``. The runtime sets its shutdown event right after writing the
  reply, so the subprocess exits 0 on its own — main only needs SIGTERM
  if the round-trip times out.
"""

from typing import Final

# Handshake (Sandbox → Main): the runtime's first frame on the channel.
# Replaces the old ``sandbox:ready`` stdout text marker — the manager
# registers a handler for this push and treats its arrival as "running",
# so stdout carries nothing but channel frames.
MSG_READY: Final = "sandbox/ready"

# Main → Sandbox
MSG_ENTRY_SETUP: Final = "sandbox/entry_setup"
MSG_ENTRY_UNLOAD: Final = "sandbox/entry_unload"
MSG_CALL_SERVICE: Final = "sandbox/call_service"
MSG_SHUTDOWN: Final = "sandbox/shutdown"

# Sandbox → Main
MSG_REGISTER_ENTITY: Final = "sandbox/register_entity"
MSG_UNREGISTER_ENTITY: Final = "sandbox/unregister_entity"
MSG_STATE_CHANGED: Final = "sandbox/state_changed"
MSG_REGISTER_SERVICE: Final = "sandbox/register_service"
MSG_UNREGISTER_SERVICE: Final = "sandbox/unregister_service"
MSG_FIRE_EVENT: Final = "sandbox/fire_event"
MSG_STORE_LOAD: Final = "sandbox/store_load"
MSG_STORE_SAVE: Final = "sandbox/store_save"
MSG_STORE_REMOVE: Final = "sandbox/store_remove"


__all__ = [
    "MSG_CALL_SERVICE",
    "MSG_ENTRY_SETUP",
    "MSG_ENTRY_UNLOAD",
    "MSG_FIRE_EVENT",
    "MSG_READY",
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
