"""Handle websocket api for Matter."""

from __future__ import annotations

from typing import Any

from matter_server.client.models.node import MatterNode
from matter_server.common.helpers.util import dataclass_to_dict
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback

from .adapter import MatterAdapter
from .api_base import (
    DEVICE_ID,
    ID,
    TYPE,
    async_get_matter_adapter,
    async_get_node,
    async_handle_failed_command,
)
from .api_lock import async_register_lock_api
from .api_lock_schedules import async_register_lock_schedules_api


@callback
def async_register_api(hass: HomeAssistant) -> None:
    """Register all of our api endpoints."""
    websocket_api.async_register_command(hass, websocket_commission)
    websocket_api.async_register_command(hass, websocket_commission_on_network)
    websocket_api.async_register_command(hass, websocket_set_thread_dataset)
    websocket_api.async_register_command(hass, websocket_set_wifi_credentials)
    websocket_api.async_register_command(hass, websocket_node_diagnostics)
    websocket_api.async_register_command(hass, websocket_ping_node)
    websocket_api.async_register_command(hass, websocket_open_commissioning_window)
    websocket_api.async_register_command(hass, websocket_remove_matter_fabric)
    websocket_api.async_register_command(hass, websocket_interview_node)
    # Register lock credential management commands
    async_register_lock_api(hass)
    # Register lock schedule management commands
    async_register_lock_schedules_api(hass)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/commission",
        vol.Required("code"): str,
        vol.Optional("network_only"): bool,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
async def websocket_commission(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
) -> None:
    """Add a device to the network and commission the device."""
    await matter.matter_client.commission_with_code(
        msg["code"], network_only=msg.get("network_only", True)
    )
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/commission_on_network",
        vol.Required("pin"): int,
        vol.Optional("ip_addr"): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
async def websocket_commission_on_network(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
) -> None:
    """Commission a device already on the network."""
    await matter.matter_client.commission_on_network(
        msg["pin"], ip_addr=msg.get("ip_addr")
    )
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/set_thread",
        vol.Required("thread_operation_dataset"): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
async def websocket_set_thread_dataset(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
) -> None:
    """Set thread dataset."""
    await matter.matter_client.set_thread_operational_dataset(
        msg["thread_operation_dataset"]
    )
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/set_wifi_credentials",
        vol.Required("network_name"): str,
        vol.Required("password"): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
async def websocket_set_wifi_credentials(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
) -> None:
    """Set WiFi credentials for a device."""
    await matter.matter_client.set_wifi_credentials(
        ssid=msg["network_name"], credentials=msg["password"]
    )
    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/node_diagnostics",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_node_diagnostics(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Gather diagnostics for the given node."""
    result = await matter.matter_client.node_diagnostics(node_id=node.node_id)
    connection.send_result(msg[ID], dataclass_to_dict(result))


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/ping_node",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_ping_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Ping node on the currently known IP-adress(es)."""
    result = await matter.matter_client.ping_node(node_id=node.node_id)
    connection.send_result(msg[ID], result)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/open_commissioning_window",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_open_commissioning_window(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Open a commissioning window to commission a device present on this controller to another."""
    result = await matter.matter_client.open_commissioning_window(node_id=node.node_id)
    connection.send_result(msg[ID], dataclass_to_dict(result))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/remove_matter_fabric",
        vol.Required(DEVICE_ID): str,
        vol.Required("fabric_index"): int,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_remove_matter_fabric(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Remove Matter fabric from a device."""
    await matter.matter_client.remove_matter_fabric(
        node_id=node.node_id, fabric_index=msg["fabric_index"]
    )
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/interview_node",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_interview_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Interview a node."""
    await matter.matter_client.interview_node(node_id=node.node_id)
    connection.send_result(msg[ID])
