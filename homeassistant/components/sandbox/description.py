"""Wire-facing entity description shared by the bridge and the proxy entities.

:class:`SandboxEntityDescription` is the flattened snapshot of a
sandbox-side entity carried by ``sandbox/register_entity``; the proxy
entities consume it and the bridge builds it from the typed proto.
Living in its own module keeps :mod:`entity` from needing anything out
of :mod:`bridge` besides the bridge type itself.
"""

from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.helpers import device_registry as dr

from ._proto import sandbox_pb2 as pb
from .messages import decode_json_dict

_LOGGER = logging.getLogger(__name__)


@dataclass
class SandboxEntityDescription:
    """Snapshot of a sandbox-side entity, sent at registration time."""

    entry_id: str
    domain: str
    sandbox_entity_id: str
    unique_id: str | None = None
    name: str | None = None
    icon: str | None = None
    has_entity_name: bool = False
    entity_category: str | None = None
    device_class: str | None = None
    supported_features: int = 0
    capabilities: dict[str, Any] = field(default_factory=dict)
    initial_state: str | None = None
    initial_attributes: dict[str, Any] = field(default_factory=dict)
    device_info: dict[str, Any] | None = None

    @classmethod
    def from_proto(cls, msg: pb.EntityDescription) -> SandboxEntityDescription:
        """Build a description from the typed ``EntityDescription`` message.

        Flattens the nested ``EntityInfo`` / ``InitialState`` sub-messages back
        into the flat shape the proxy entities consume.
        """
        description = msg.info.description
        initial = msg.initial
        device_info = (
            _deserialise_device_info(msg.info.device_info)
            if msg.info.HasField("device_info")
            else None
        )
        return cls(
            entry_id=msg.entry_id,
            domain=msg.domain,
            sandbox_entity_id=msg.sandbox_entity_id,
            unique_id=msg.unique_id if msg.HasField("unique_id") else None,
            name=description.name if description.HasField("name") else None,
            icon=description.icon if description.HasField("icon") else None,
            has_entity_name=msg.has_entity_name,
            entity_category=(
                description.entity_category
                if description.HasField("entity_category")
                else None
            ),
            device_class=(
                description.device_class
                if description.HasField("device_class")
                else None
            ),
            supported_features=description.supported_features,
            capabilities=decode_json_dict(initial.capabilities),
            initial_state=initial.state if initial.HasField("state") else None,
            initial_attributes=decode_json_dict(initial.attributes),
            device_info=device_info,
        )


_DEVICE_INFO_STR_FIELDS = (
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


def _deserialise_device_info(info: pb.DeviceInfo) -> dict[str, Any] | None:
    """Rebuild a ``DeviceInfo`` TypedDict from the typed proto.

    ``identifiers`` / ``connections`` come back as sets of tuples and
    ``via_device`` as a tuple — the shapes
    :func:`device_registry.async_get_or_create` validates. ``entry_type`` is
    rebuilt as a :class:`DeviceEntryType` enum value.
    """
    out: dict[str, Any] = {}
    if info.identifiers:
        out["identifiers"] = {(pair.key, pair.value) for pair in info.identifiers}
    if info.connections:
        out["connections"] = {(pair.key, pair.value) for pair in info.connections}
    if info.HasField("via_device"):
        out["via_device"] = (info.via_device.key, info.via_device.value)
    if info.entry_type:
        try:
            out["entry_type"] = dr.DeviceEntryType(info.entry_type)
        except ValueError:
            _LOGGER.debug(
                "register_entity: unknown entry_type %r — dropping", info.entry_type
            )
    for field_name in _DEVICE_INFO_STR_FIELDS:
        value = getattr(info, field_name)
        if value:
            out[field_name] = value
    return out or None


__all__ = ["SandboxEntityDescription"]
