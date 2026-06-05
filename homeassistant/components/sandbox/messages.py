"""Typed protobuf message registry + dynamic-field helpers.

This module is the codec's view of the wire: the ``type → (request_cls,
result_cls)`` registry plus the small Struct/ListValue helpers that carry the
genuinely dynamic payloads (service_data, target, state attributes,
capabilities, the wrapped Store envelope, flow ``data``/``errors``/``context``)
and the serialized voluptuous schema.

Mirrored verbatim across the no-cross-import boundary, exactly like
:mod:`channel` / :mod:`protocol`: the same file lives at
``hass_client.messages``. The relative ``._proto`` import resolves to each
side's own checked-in gencode, so the two copies are byte-identical.

Numbers note: ``google.protobuf.Struct`` stores every number as a double, so
an ``int`` that crosses inside a dynamic field comes back as a ``float``
(``255`` → ``255.0``). Python's ``==`` treats the two as equal, so dict
comparisons still hold; only an ``isinstance(x, int)`` check would notice.
Everything with integer semantics that matters (``version``, ``minor_version``,
``supported_features``) is an explicit ``int32`` field, not a Struct value.
"""

from typing import Any

from google.protobuf.message import Message

# pylint: disable-next=no-name-in-module
from google.protobuf.struct_pb2 import ListValue, Struct, Value

from ._proto import sandbox_pb2 as pb

# Wire type → (request message class, result message class). The result class
# is ``None`` for one-way pushes (ready / state_changed / fire_event). The
# codec resolves these from ``frame.type`` on both encode and decode.
REGISTRY: dict[str, tuple[type[Message], type[Message] | None]] = {
    # handshake (push)
    "sandbox/ready": (pb.Ready, None),
    # main → sandbox
    "sandbox/entry_setup": (pb.EntrySetup, pb.EntrySetupResult),
    "sandbox/entry_unload": (pb.EntryUnload, pb.EntryUnloadResult),
    "sandbox/call_service": (pb.CallService, pb.CallServiceResult),
    "sandbox/get_translations": (pb.GetTranslations, pb.GetTranslationsResult),
    "sandbox/shutdown": (pb.Shutdown, pb.ShutdownResult),
    "sandbox/ping": (pb.Ping, pb.PingResult),
    "sandbox/flow_init": (pb.FlowInit, pb.FlowResult),
    "sandbox/flow_step": (pb.FlowStep, pb.FlowResult),
    "sandbox/flow_abort": (pb.FlowAbort, pb.FlowAbortResult),
    # sandbox → main
    "sandbox/register_entity": (pb.EntityDescription, pb.RegisterEntityResult),
    "sandbox/unregister_entity": (pb.UnregisterEntity, pb.UnregisterEntityResult),
    "sandbox/state_changed": (pb.StateChanged, None),
    "sandbox/register_service": (pb.RegisterService, pb.RegisterServiceResult),
    "sandbox/unregister_service": (
        pb.UnregisterService,
        pb.UnregisterServiceResult,
    ),
    "sandbox/fire_event": (pb.FireEvent, None),
    "sandbox/store_load": (pb.StoreLoad, pb.StoreLoadResult),
    "sandbox/store_save": (pb.StoreSave, pb.StoreSaveResult),
    "sandbox/store_remove": (pb.StoreRemove, pb.StoreRemoveResult),
}


# --- Struct / ListValue helpers -------------------------------------------


def _value_to_py(value: Value) -> Any:
    """Convert one ``google.protobuf.Value`` into a plain Python value."""
    kind = value.WhichOneof("kind")
    if kind == "null_value" or kind is None:
        return None
    if kind == "number_value":
        return value.number_value
    if kind == "string_value":
        return value.string_value
    if kind == "bool_value":
        return value.bool_value
    if kind == "struct_value":
        return struct_to_dict(value.struct_value)
    return [_value_to_py(item) for item in value.list_value.values]


def struct_to_dict(struct: Struct) -> dict[str, Any]:
    """Convert a ``Struct`` into a plain ``dict`` (empty Struct → ``{}``)."""
    return {key: _value_to_py(val) for key, val in struct.fields.items()}


def dict_to_struct(data: dict[str, Any] | None) -> Struct:
    """Convert a ``dict`` (or ``None``) into a ``Struct``."""
    struct = Struct()
    if data:
        struct.update(data)
    return struct


def listvalue_to_list(list_value: ListValue) -> list[Any]:
    """Convert a ``ListValue`` into a plain ``list``."""
    return [_value_to_py(item) for item in list_value.values]


def list_to_listvalue(items: list[Any] | None) -> ListValue:
    """Convert a ``list`` (or ``None``) into a ``ListValue``."""
    list_value = ListValue()
    if items:
        list_value.extend(items)
    return list_value


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
        msg.initial.capabilities.update(capabilities)
    if initial_attributes:
        msg.initial.attributes.update(initial_attributes)
    return msg


__all__ = [
    "REGISTRY",
    "device_info_to_proto",
    "dict_to_struct",
    "list_to_listvalue",
    "listvalue_to_list",
    "make_entity_description",
    "struct_to_dict",
]
