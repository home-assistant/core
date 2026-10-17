"""Wire-protocol constants, typed proto registry + dynamic-payload JSON codec."""

from typing import Any, Final

from google.protobuf.message import Message
import orjson

from homeassistant.helpers.json import json_encoder_default

from ._proto import sandbox_pb2 as pb

# Readiness is a protocol message; stdout is reserved for channel frames.
MSG_READY: Final = "sandbox/ready"

# Main → Sandbox
MSG_ENTRY_SETUP: Final = "sandbox/entry_setup"
MSG_ENTRY_UPDATE: Final = "sandbox/entry_update"
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
    MSG_ENTRY_UPDATE: (pb.EntryUpdate, pb.EntryUpdateResult),
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
    """HA's JSON encoder, with a ``str(obj)`` fallback for unknown objects."""
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
    """Build a ``DeviceInfo`` proto from the JSON-flattened device_info dict."""
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
    config_subentry_id: str | None = None,
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
    """Build a nested ``EntityDescription`` proto from flat fields."""
    msg = pb.EntityDescription(
        entry_id=entry_id,
        domain=domain,
        sandbox_entity_id=sandbox_entity_id,
        has_entity_name=has_entity_name,
    )
    if unique_id is not None:
        msg.unique_id = unique_id
    if config_subentry_id is not None:
        msg.config_subentry_id = config_subentry_id
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


def entry_to_setup_proto(entry: Any) -> pb.EntrySetup:
    """Serialise the entry-identity fields of a ConfigEntry into EntrySetup."""
    msg = pb.EntrySetup(
        entry_id=entry.entry_id,
        domain=entry.domain,
        title=entry.title,
        data=encode_json(dict(entry.data)),
        options=encode_json(dict(entry.options)),
        source=entry.source,
        version=entry.version,
        minor_version=entry.minor_version,
        subentries=encode_json([item.as_dict() for item in entry.subentries.values()]),
        discovery_keys=encode_json(entry.as_dict()["discovery_keys"]),
        pref_disable_new_entities=entry.pref_disable_new_entities,
        pref_disable_polling=entry.pref_disable_polling,
    )
    if entry.unique_id is not None:
        msg.unique_id = entry.unique_id
    return msg


def core_config_to_proto(config: Any) -> pb.CoreConfig:
    """Snapshot a hass ``Config`` into the wire ``CoreConfig`` message."""
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
    "MSG_ENTRY_UPDATE",
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
