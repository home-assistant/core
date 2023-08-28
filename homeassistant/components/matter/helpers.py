"""Provide integration helpers that are aware of the matter integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, ID_TYPE_DEVICE_ID

if TYPE_CHECKING:
    from matter_server.client.models.node import MatterEndpoint, MatterNode
    from matter_server.common.models import ServerInfoMessage

    from .adapter import MatterAdapter


@dataclass
class MatterEntryData:
    """Hold Matter data for the config entry."""

    adapter: MatterAdapter
    listen_task: asyncio.Task


@callback
def get_matter(hass: HomeAssistant) -> MatterAdapter:
    """Return MatterAdapter instance."""
    # NOTE: This assumes only one Matter connection/fabric can exist.
    # Shall we support connecting to multiple servers in the client or by
    # config entries? In case of the config entry we need to fix this.
    matter_entry_data: MatterEntryData = next(iter(hass.data[DOMAIN].values()))
    return matter_entry_data.adapter


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


def get_device_id(
    server_info: ServerInfoMessage,
    endpoint: MatterEndpoint,
) -> str:
    """Return HA device_id for the given MatterEndpoint."""
    operational_instance_id = get_operational_instance_id(server_info, endpoint.node)
    # Append endpoint ID if this endpoint is a bridged or composed device
    if endpoint.is_composed_device:
        compose_parent = endpoint.node.get_compose_parent(endpoint.endpoint_id)
        assert compose_parent is not None
        postfix = str(compose_parent.endpoint_id)
    elif endpoint.is_bridged_device:
        postfix = str(endpoint.endpoint_id)
    else:
        # this should be compatible with previous versions
        postfix = "MatterNodeDevice"
    return f"{operational_instance_id}-{postfix}"


async def get_node_from_device_entry(
    hass: HomeAssistant, device: dr.DeviceEntry
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
        raise ValueError(f"Device {device.id} is not a Matter device")

    device_id = device_id_full.lstrip(device_id_type_prefix)
    matter_client = matter.matter_client
    server_info = matter_client.server_info

    if server_info is None:
        raise RuntimeError("Matter server information is not available")

    node = next(
        (
            node
            for node in matter_client.get_nodes()
            for endpoint in node.endpoints.values()
            if get_device_id(server_info, endpoint) == device_id
        ),
        None,
    )

    return node
