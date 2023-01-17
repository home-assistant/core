"""Provide integration helpers that are aware of the matter integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

if TYPE_CHECKING:
    from matter_server.common.models.node_device import MatterNode
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
    # Shall we support connecting to multiple servers in the client or by config entries?
    # In case of the config entry we need to fix this.
    matter_entry_data: MatterEntryData = next(iter(hass.data[DOMAIN].values()))
    return matter_entry_data.adapter


def get_node_unique_id(
    server_info: ServerInfo, node: MatterNode, is_bridge: bool = False
) -> str:
    """Return unique id for a Matter node based on `Operational Instance Name`."""
    fab_id_hex = f"{server_info.compressed_fabric_id:016X}"
    node_id_hex = f"{node.node_id:016X}"
    node_unique_id = f"{fab_id_hex}-{node_id_hex}"
    if is_bridge:
        # create 'virtual' device(id) for a root/bridge device
        node_unique_id += "-bridge"
    return node_unique_id
