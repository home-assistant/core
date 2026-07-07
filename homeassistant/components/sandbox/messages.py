"""Wire-protocol constants, typed proto registry + dynamic-payload JSON codec.

The integration and the sandbox runtime exchange typed protobuf messages over
the :class:`Channel`. Each message type is namespaced ``sandbox/…``; this
module holds the ``MSG_*`` type-string constants, the ``type → (request_cls,
result_cls)`` registry (the codec resolves it on both encode and decode), and
the single encoder/decoder pair for the genuinely dynamic payloads
(service_data, target, state attributes, capabilities, the wrapped Store
envelope, flow ``data``/``errors``/``context``, the serialized voluptuous
schema). Those cross as orjson-encoded JSON in ``bytes`` fields: measured ~13x
faster than the ``google.protobuf.Struct`` fields they replaced, with native
number fidelity (Struct stored every number as a double) and one coercer —
:func:`encode_json` embeds HA's rich-type JSON encoding, so producers never
pre-coerce.

Mirrored verbatim across the no-cross-import boundary, exactly like
:mod:`channel`: the same file lives at ``hass_client.messages``. The relative
``._proto`` import resolves to each side's own checked-in gencode, so the two
copies are byte-identical — and ``sandbox/proto/check_mirror_drift.sh`` fails
the build if they drift apart.

Each ``MSG_*`` type maps to a request/result proto message pair in
``REGISTRY``, generated from ``sandbox/proto/sandbox.proto``. The payload
shapes described below are the *logical* contract for each call — they are
carried as those typed proto messages, not free-form dicts. A registry-free
line-oriented JSON codec lives in the test helpers as the channel-core
test/debug wire.

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
* ``sandbox/entity_query`` — generic request/response RPC for the
  server-side entity queries with no ``SupportsResponse`` service to ride
  (media search, update release notes, vacuum segments, the WS-only calendar
  event edits). Payload ``{sandbox_entity_id, method, args, context_id}``;
  the sandbox resolves the entity, invokes ``method`` with ``args`` as kwargs,
  and returns the serialised result wrapped as ``{"value": <return>}``.
  Ops that map to a ``SupportsResponse`` service use ``call_service`` instead.
* ``sandbox/get_translations`` — pull a sandboxed integration's frontend
  translation strings. Payload ``{language, domains: [str]}`` (main batches
  every owned custom domain of one group into a single request). Response
  ``{language, strings: {domain: <raw strings.json dict>}}`` — the
  un-flattened nesting a ``translations/<lang>.json`` holds, with ``title``
  pre-filled from the integration name (main has no ``Integration`` for a
  custom domain, so it cannot run that fallback). Built-in domains never
  cross the wire — main reads its byte-identical disk copy.
* ``sandbox/ping`` — liveness probe; the runtime echoes an empty result.
* ``sandbox/flow_init`` / ``sandbox/flow_step`` / ``sandbox/flow_abort`` —
  config-flow forwarding: bootstrap a sandbox-side flow, drive one step,
  tear a flow down. See ``proxy_flow`` (main) / ``flow_runner`` (sandbox).

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

from typing import Any, Final

from google.protobuf.message import Message
import orjson

from homeassistant.helpers.json import json_encoder_default

from ._proto import sandbox_pb2 as pb

# Handshake (Sandbox → Main): the runtime's first frame on the channel.
# Replaces the old ``sandbox:ready`` stdout text marker — the manager
# registers a handler for this push and treats its arrival as "running",
# so stdout carries nothing but channel frames.
MSG_READY: Final = "sandbox/ready"

# Main → Sandbox
MSG_ENTRY_SETUP: Final = "sandbox/entry_setup"
MSG_ENTRY_UNLOAD: Final = "sandbox/entry_unload"
MSG_CALL_SERVICE: Final = "sandbox/call_service"
MSG_ENTITY_QUERY: Final = "sandbox/entity_query"
MSG_GET_TRANSLATIONS: Final = "sandbox/get_translations"
MSG_SHUTDOWN: Final = "sandbox/shutdown"
MSG_PING: Final = "sandbox/ping"
MSG_FLOW_INIT: Final = "sandbox/flow_init"
MSG_FLOW_STEP: Final = "sandbox/flow_step"
MSG_FLOW_ABORT: Final = "sandbox/flow_abort"

# Sandbox → Main
MSG_REGISTER_ENTITY: Final = "sandbox/register_entity"
MSG_UNREGISTER_ENTITY: Final = "sandbox/unregister_entity"
MSG_STATE_CHANGED: Final = "sandbox/state_changed"
MSG_REGISTER_SERVICE: Final = "sandbox/register_service"
MSG_UNREGISTER_SERVICE: Final = "sandbox/unregister_service"
MSG_FIRE_EVENT: Final = "sandbox/fire_event"
# main -> sandbox one-way push: live core-config update (entry_setup carries
# the initial snapshot; this keeps a running sandbox in step when the user
# changes the home location / units / language on main).
MSG_CORE_CONFIG = "sandbox/core_config"
MSG_STORE_LOAD: Final = "sandbox/store_load"
MSG_STORE_SAVE: Final = "sandbox/store_save"
MSG_STORE_REMOVE: Final = "sandbox/store_remove"

# Wire type → (request message class, result message class). The result class
# is ``None`` for one-way pushes (ready / state_changed / fire_event). The
# codec resolves these from ``frame.type`` on both encode and decode.
REGISTRY: dict[str, tuple[type[Message], type[Message] | None]] = {
    # handshake (push)
    MSG_READY: (pb.Ready, None),
    # main → sandbox
    MSG_ENTRY_SETUP: (pb.EntrySetup, pb.EntrySetupResult),
    MSG_ENTRY_UNLOAD: (pb.EntryUnload, pb.EntryUnloadResult),
    MSG_CALL_SERVICE: (pb.CallService, pb.CallServiceResult),
    MSG_ENTITY_QUERY: (pb.EntityQuery, pb.EntityQueryResult),
    MSG_GET_TRANSLATIONS: (pb.GetTranslations, pb.GetTranslationsResult),
    MSG_SHUTDOWN: (pb.Shutdown, pb.ShutdownResult),
    MSG_PING: (pb.Ping, pb.PingResult),
    MSG_FLOW_INIT: (pb.FlowInit, pb.FlowResult),
    MSG_FLOW_STEP: (pb.FlowStep, pb.FlowResult),
    MSG_FLOW_ABORT: (pb.FlowAbort, pb.FlowAbortResult),
    # sandbox → main
    MSG_REGISTER_ENTITY: (pb.EntityDescription, pb.RegisterEntityResult),
    MSG_UNREGISTER_ENTITY: (pb.UnregisterEntity, pb.UnregisterEntityResult),
    MSG_STATE_CHANGED: (pb.StateChanged, None),
    MSG_REGISTER_SERVICE: (pb.RegisterService, pb.RegisterServiceResult),
    MSG_UNREGISTER_SERVICE: (
        pb.UnregisterService,
        pb.UnregisterServiceResult,
    ),
    MSG_FIRE_EVENT: (pb.FireEvent, None),
    MSG_CORE_CONFIG: (pb.CoreConfig, None),
    MSG_STORE_LOAD: (pb.StoreLoad, pb.StoreLoadResult),
    MSG_STORE_SAVE: (pb.StoreSave, pb.StoreSaveResult),
    MSG_STORE_REMOVE: (pb.StoreRemove, pb.StoreRemoveResult),
}


# --- dynamic-payload JSON codec --------------------------------------------


def _default(obj: Any) -> Any:
    """HA's JSON encoder, with a ``str(obj)`` fallback for unknown objects.

    The sandbox forwards integration-supplied payloads that can hold
    arbitrary domain objects; the fallback keeps a single odd field from
    raising and dropping the whole best-effort payload.
    """
    try:
        return json_encoder_default(obj)
    except TypeError:
        return str(obj)


def encode_json(value: Any) -> bytes:
    """Encode a dynamic payload as orjson bytes, coercing rich HA types."""
    return orjson.dumps(value, option=orjson.OPT_NON_STR_KEYS, default=_default)


def decode_json(data: bytes) -> Any:
    """Decode a dynamic payload (empty bytes → ``None``)."""
    if not data:
        return None
    return orjson.loads(data)


def decode_json_dict(data: bytes) -> dict[str, Any]:
    """Decode a dynamic dict payload (empty bytes → ``{}``)."""
    if not data:
        return {}
    decoded: dict[str, Any] = orjson.loads(data)
    return decoded


# --- DeviceInfo bridging --------------------------------------------------

# Scalar string fields of the DeviceInfo proto, copied through verbatim when
# present in the JSON-flattened device_info dict.
_DEVICE_INFO_SCALARS = (
    "entry_type",
    "name",
    "manufacturer",
    "model",
    "model_id",
    "sw_version",
    "hw_version",
    "serial_number",
    "suggested_area",
    "configuration_url",
    "default_name",
    "default_manufacturer",
    "default_model",
    "translation_key",
)


def device_info_to_proto(flat: dict[str, Any] | None) -> pb.DeviceInfo | None:
    """Build a ``DeviceInfo`` proto from the JSON-flattened device_info dict.

    The sandbox-side serializer (``entity_bridge._serialise_device_info``)
    already flattens sets/tuples/enums: ``identifiers`` / ``connections`` are
    lists of two-element lists, ``via_device`` is a two-element list, and
    ``entry_type`` is the enum's string value. This maps that shape onto the
    explicit proto fields.
    """
    if not flat:
        return None
    info = pb.DeviceInfo()
    for key, raw in flat.items():
        if raw is None:
            continue
        if key in ("identifiers", "connections"):
            for pair in raw:
                if len(pair) == 2:
                    getattr(info, key).add(key=str(pair[0]), value=str(pair[1]))
        elif key == "via_device":
            if len(raw) == 2:
                info.via_device.key = str(raw[0])
                info.via_device.value = str(raw[1])
        elif key in _DEVICE_INFO_SCALARS:
            setattr(info, key, str(raw))
    return info


def make_entity_description(
    *,
    entry_id: str,
    domain: str,
    sandbox_entity_id: str,
    unique_id: str | None = None,
    name: str | None = None,
    icon: str | None = None,
    has_entity_name: bool = False,
    entity_category: str | None = None,
    device_class: str | None = None,
    supported_features: int = 0,
    translation_key: str | None = None,
    capabilities: dict[str, Any] | None = None,
    initial_state: str | None = None,
    initial_attributes: dict[str, Any] | None = None,
    device_info: dict[str, Any] | None = None,
) -> pb.EntityDescription:
    """Build a nested ``EntityDescription`` proto from flat fields.

    Used by the sandbox entity bridge and by tests so neither has to hand-nest
    the ``EntityInfo`` / ``InitialState`` sub-messages. ``device_info`` is the
    JSON-flattened dict the entity bridge produces (see
    :func:`device_info_to_proto`).
    """
    msg = pb.EntityDescription(
        entry_id=entry_id,
        domain=domain,
        sandbox_entity_id=sandbox_entity_id,
        has_entity_name=has_entity_name,
    )
    if unique_id is not None:
        msg.unique_id = unique_id
    description = msg.info.description
    if name is not None:
        description.name = name
    if icon is not None:
        description.icon = icon
    if entity_category is not None:
        description.entity_category = entity_category
    if device_class is not None:
        description.device_class = device_class
    description.supported_features = int(supported_features or 0)
    if translation_key is not None:
        description.translation_key = translation_key
    device = device_info_to_proto(device_info)
    if device is not None:
        msg.info.device_info.CopyFrom(device)
    if initial_state is not None:
        msg.initial.state = initial_state
    if capabilities:
        msg.initial.capabilities = encode_json(capabilities)
    if initial_attributes:
        msg.initial.attributes = encode_json(initial_attributes)
    return msg


def core_config_to_proto(config: Any) -> pb.CoreConfig:
    """Snapshot a hass ``Config`` into the wire ``CoreConfig`` message.

    Shared by the ``entry_setup`` payload and the live
    ``sandbox/core_config`` push so the two can't drift.
    """
    msg = pb.CoreConfig(
        latitude=config.latitude,
        longitude=config.longitude,
        elevation=config.elevation,
        time_zone=config.time_zone,
        # The unit system carries no public name accessor; core itself reads
        # ``units._name`` when persisting (core_config.py).
        unit_system=config.units._name,  # noqa: SLF001
        language=config.language,
        currency=config.currency,
        location_name=config.location_name,
    )
    if config.country is not None:
        msg.country = config.country
    return msg


__all__ = [
    "MSG_CALL_SERVICE",
    "MSG_ENTITY_QUERY",
    "MSG_ENTRY_SETUP",
    "MSG_ENTRY_UNLOAD",
    "MSG_FIRE_EVENT",
    "MSG_FLOW_ABORT",
    "MSG_FLOW_INIT",
    "MSG_FLOW_STEP",
    "MSG_GET_TRANSLATIONS",
    "MSG_PING",
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
    "REGISTRY",
    "core_config_to_proto",
    "decode_json",
    "decode_json_dict",
    "device_info_to_proto",
    "encode_json",
    "make_entity_description",
]
