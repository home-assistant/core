"""Provide integration helpers that are aware of the matter integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, ID_TYPE_DEVICE_ID

if TYPE_CHECKING:
    from matter_server.common.models.node import MatterNode
    from matter_server.common.models.node_device import AbstractMatterNodeDevice
    from matter_server.common.models.server_information import ServerInfo

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
    server_info: ServerInfo,
    node: MatterNode,
) -> str:
    """Return `Operational Instance Name` for given MatterNode."""
    fabric_id_hex = f"{server_info.compressed_fabric_id:016X}"
    node_id_hex = f"{node.node_id:016X}"
    # Operational instance id matches the mDNS advertisement for the node
    # this is the recommended ID to recognize a unique matter node (within a fabric).
    return f"{fabric_id_hex}-{node_id_hex}"


def get_device_id(
    server_info: ServerInfo,
    node_device: AbstractMatterNodeDevice,
) -> str:
    """Return HA device_id for the given MatterNodeDevice."""
    operational_instance_id = get_operational_instance_id(
        server_info, node_device.node()
    )
    # Append nodedevice(type) to differentiate between a root node
    # and bridge within Home Assistant devices.
    return f"{operational_instance_id}-{node_device.__class__.__name__}"


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
            for node in await matter_client.get_nodes()
            for node_device in node.node_devices
            if get_device_id(server_info, node_device) == device_id
        ),
        None,
    )

    return node
