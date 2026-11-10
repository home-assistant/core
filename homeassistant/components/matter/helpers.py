"""Provide integration helpers that are aware of the matter integration."""

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from matter_server.client.models.device_types import OnOffPlugInUnit

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, ID_TYPE_DEVICE_ID
from .semantic_tags import ChildDeviceName, resolve_group_names

if TYPE_CHECKING:
    from matter_ble_proxy import MatterBleProxy
    from matter_server.client.models.device_types import DeviceType
    from matter_server.client.models.node import MatterEndpoint, MatterNode
    from matter_server.common.models import ServerInfoMessage

    from .adapter import MatterAdapter
    from .models import MatterEntityInfo


# Application (output) device types that each represent an independent physical
# sub-unit of a node. When a node exposes the same one of these on more than one
# endpoint (e.g. the sockets of a multi-socket plug), and semantic tags or vendor
# labels name each such endpoint, each one becomes its own child device instead
# of collapsing onto the node device with a numeric entity name suffix.
# Stateless controls (Generic Switch) and utility endpoints (Power Source,
# Electrical Sensor, ...) are deliberately excluded.
# The allowlist is intentionally limited to device types we have test fixtures
# for; it can be extended (e.g. lights, covers) as fixtures become available.
CHILD_DEVICE_TYPES: set[type[DeviceType]] = {
    OnOffPlugInUnit,
}


class MissingNode(HomeAssistantError):
    """Exception raised when we can't find a node."""


@dataclass
class MatterEntryData:
    """Hold Matter data for the config entry."""

    adapter: MatterAdapter
    listen_task: asyncio.Task
    ble_proxy: MatterBleProxy | None = None


type MatterConfigEntry = ConfigEntry[MatterEntryData]


@callback
def get_matter(hass: HomeAssistant) -> MatterAdapter:
    """Return MatterAdapter instance."""
    # NOTE: This assumes only one Matter connection/fabric can exist.
    # Shall we support connecting to multiple servers in the client or by
    # config entries? In case of the config entry we need to fix this.
    entries: list[MatterConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data.adapter


def get_discovery_key(endpoint: MatterEndpoint, entity_info: MatterEntityInfo) -> str:
    """Return the key under which the adapter tracks a discovered entity."""
    return (
        f"{entity_info.platform}_{endpoint.node.node_id}_{endpoint.endpoint_id}_"
        f"{entity_info.primary_attribute.cluster_id}_"
        f"{entity_info.primary_attribute.attribute_id}_"
        f"{entity_info.entity_description.key}"
    )


def get_operational_instance_id(
    server_info: ServerInfoMessage,
    node: MatterNode,
) -> str:
    """Return `Operational Instance Name` for given MatterNode."""
    fabric_id_hex = f"{server_info.compressed_fabric_id:016X}"
    node_id_hex = f"{node.node_id:016X}"
    # Operational instance id matches the mDNS advertisement for the node
    # this is the recommended ID to recognize a unique matter node (within a fabric).
    return f"{fabric_id_hex}-{node_id_hex}"


def get_device_endpoint(endpoint: MatterEndpoint) -> MatterEndpoint:
    """Return the endpoint the HA device for the given MatterEndpoint is derived from.

    All endpoints of a composed device are represented by a single HA device, derived
    from the compose parent.
    Example: Philips Hue motion sensor on Hue Hub (bridged to Matter).
    """
    return endpoint.node.get_compose_parent(endpoint.endpoint_id) or endpoint


def _get_device_id_for_device_endpoint(
    server_info: ServerInfoMessage, device_endpoint: MatterEndpoint
) -> str:
    """Return HA device_id for the endpoint a device is derived from."""
    operational_instance_id = get_operational_instance_id(
        server_info, device_endpoint.node
    )
    if device_endpoint.is_bridged_device:
        # Append endpoint ID if this endpoint is a bridged device
        postfix = str(device_endpoint.endpoint_id)
    else:
        # this should be compatible with previous versions
        postfix = "MatterNodeDevice"
    return f"{operational_instance_id}-{postfix}"


def get_device_id(
    server_info: ServerInfoMessage,
    endpoint: MatterEndpoint,
) -> str:
    """Return HA device_id for the given MatterEndpoint."""
    return _get_device_id_for_device_endpoint(
        server_info, get_device_endpoint(endpoint)
    )


def get_legacy_device_id(
    server_info: ServerInfoMessage,
    endpoint: MatterEndpoint,
) -> str:
    """Return the device_id matter-python-client <1.5.0 would have generated.

    matter-python-client 1.5.0 changed `get_compose_parent()` to resolve to the top
    of a composition instead of the closest parent, which can change the device_id
    (and therefore entity unique_id) of a part nested below another part. Only used
    to find entity registry entries that still use the pre-1.5.0 unique_id so they
    can be migrated.
    """
    closest_parent = endpoint.node.get_closest_compose_parent(endpoint.endpoint_id)
    return _get_device_id_for_device_endpoint(server_info, closest_parent or endpoint)


def get_entity_unique_id(
    device_id: str, endpoint: MatterEndpoint, entity_info: MatterEntityInfo
) -> str:
    """Return the unique_id for an entity discovered on a MatterEndpoint."""
    primary_attribute = entity_info.primary_attribute
    return (
        f"{device_id}-"
        f"{endpoint.endpoint_id}-"
        f"{entity_info.entity_description.key}-"
        f"{primary_attribute.cluster_id}-"
        f"{primary_attribute.attribute_id}"
    )


def get_child_device_id(
    server_info: ServerInfoMessage,
    endpoint: MatterEndpoint,
) -> str:
    """Return HA device_id for the child device of the given MatterEndpoint.

    Only meaningful for endpoints that satisfy `endpoint_requires_child_device`,
    which map to the node device, so `get_device_id` returns the node device id
    (no endpoint suffix) and the child device id carries the endpoint index exactly
    once. For any other endpoint it only ever serves as a guaranteed-miss lookup
    key and never names a real device.
    """
    return f"{get_device_id(server_info, endpoint)}-{endpoint.endpoint_id}"


def _endpoint_maps_to_node_device(endpoint: MatterEndpoint) -> bool:
    """Return if the endpoint's entities collapse onto the node (parent) device.

    False for the root endpoint, bridged endpoints (already separate HA devices)
    and composed-part endpoints (collapsed onto their compose parent device). Only
    these node-device endpoints can collide with, or be split off from, each other.
    """
    node = endpoint.node
    return not (
        node.is_bridge_device
        or endpoint.endpoint_id == 0
        or endpoint.is_bridged_device
        or node.get_compose_parent(endpoint.endpoint_id) is not None
    )


def get_child_device_names(node: MatterNode) -> dict[int, ChildDeviceName]:
    """Return the child device name of every endpoint of the node that splits.

    Endpoints that map to the node device and are linked by sharing a device type
    of CHILD_DEVICE_TYPES form a sibling group, e.g. the sockets of a multi-socket
    plug. A group splits into child devices only when one name source (semantic
    tags or vendor labels) names every endpoint of the group with distinct names,
    and those names don't collide with the names of another group of the node.
    An endpoint that isn't in the result doesn't split.
    """
    groups: list[list[MatterEndpoint]] = []
    for endpoint in node.endpoints.values():
        if not _endpoint_maps_to_node_device(endpoint):
            continue
        if not (splittable_types := CHILD_DEVICE_TYPES & endpoint.device_types):
            continue
        linked = [
            group
            for group in groups
            if any(splittable_types & other.device_types for other in group)
        ]
        groups = [group for group in groups if group not in linked]
        groups.append([endpoint, *(other for group in linked for other in group)])

    group_names = [
        names
        for group in groups
        if len(group) > 1 and (names := resolve_group_names(group)) is not None
    ]
    child_device_names: dict[int, ChildDeviceName] = {}
    for names in group_names:
        keys = {name.comparison_key for name in names.values()}
        if any(
            other is not names
            and keys & {name.comparison_key for name in other.values()}
            for other in group_names
        ):
            continue
        child_device_names.update(names)
    return child_device_names


def endpoint_requires_child_device(endpoint: MatterEndpoint) -> bool:
    """Return if the endpoint should be represented as its own child device.

    True for an endpoint of a sibling group that splits into named child devices,
    see `get_child_device_names`. Every entity of such an endpoint is then placed
    on its own child device.
    """
    # Skip naming the whole node for endpoints that can never split.
    if not _endpoint_maps_to_node_device(endpoint) or not (
        CHILD_DEVICE_TYPES & endpoint.device_types
    ):
        return False
    return endpoint.endpoint_id in get_child_device_names(endpoint.node)


def get_node_device_identifier(
    server_info: ServerInfoMessage, node_id: int
) -> tuple[str, str]:
    """Return the device registry identifier for the node-level device of a node."""
    fabric_id_hex = f"{server_info.compressed_fabric_id:016X}"
    node_id_hex = f"{node_id:016X}"
    return (
        DOMAIN,
        f"{ID_TYPE_DEVICE_ID}_{fabric_id_hex}-{node_id_hex}-MatterNodeDevice",
    )


@callback
def node_from_ha_device_id(hass: HomeAssistant, ha_device_id: str) -> MatterNode | None:
    """Get node id from ha device id."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(ha_device_id)
    if device is None:
        raise MissingNode(f"Invalid device ID: {ha_device_id}")
    return get_node_from_device_entry(hass, device)


@callback
def get_node_from_device_entry(
    hass: HomeAssistant, device: dr.AnyDeviceEntry
) -> MatterNode | None:
    """Return MatterNode from device entry."""
    matter = get_matter(hass)
    device_id_type_prefix = f"{ID_TYPE_DEVICE_ID}_"
    device_id_full = next(
        (
            identifier[1]
            for identifier in device.identifiers
            if identifier[0] == DOMAIN
            and identifier[1].startswith(device_id_type_prefix)
        ),
        None,
    )

    if device_id_full is None:
        return None

    device_id = device_id_full.lstrip(device_id_type_prefix)
    matter_client = matter.matter_client
    server_info = matter_client.server_info

    if server_info is None:
        raise RuntimeError("Matter server information is not available")

    return next(
        (
            node
            for node in matter_client.get_nodes()
            for endpoint in node.endpoints.values()
            if device_id
            in (
                get_device_id(server_info, endpoint),
                get_child_device_id(server_info, endpoint),
            )
        ),
        None,
    )
