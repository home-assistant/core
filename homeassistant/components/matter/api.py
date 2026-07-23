"""Handle websocket api for Matter."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from matter_server.client.exceptions import ServerVersionTooOld
from matter_server.client.models.node import MatterNode
from matter_server.common.errors import MatterError
from matter_server.common.helpers.util import dataclass_to_dict
from matter_server.common.models import EventType, NetworkTopology
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ERR_NOT_SUPPORTED, ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .adapter import MatterAdapter
from .helpers import (
    MissingNode,
    get_matter,
    get_node_device_identifier,
    node_from_ha_device_id,
)

ID = "id"
TYPE = "type"
DEVICE_ID = "device_id"


ERROR_NODE_NOT_FOUND = "node_not_found"

# minimum server schema version that provides network topology
TOPOLOGY_SCHEMA_VERSION = 13


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
    websocket_api.async_register_command(hass, websocket_network_topology)
    websocket_api.async_register_command(hass, websocket_subscribe_network_topology)


def async_get_node(
    func: Callable[
        [HomeAssistant, ActiveConnection, dict[str, Any], MatterAdapter, MatterNode],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    [HomeAssistant, ActiveConnection, dict[str, Any], MatterAdapter],
    Coroutine[Any, Any, None],
]:
    """Decorate async function to get node."""

    @wraps(func)
    async def async_get_node_func(
        hass: HomeAssistant,
        connection: ActiveConnection,
        msg: dict[str, Any],
        matter: MatterAdapter,
    ) -> None:
        """Provide user specific data and store to function."""
        node = node_from_ha_device_id(hass, msg[DEVICE_ID])
        if not node:
            raise MissingNode(
                f"Could not resolve Matter node from device id {msg[DEVICE_ID]}"
            )
        await func(hass, connection, msg, matter, node)

    return async_get_node_func


def async_get_matter_adapter(
    func: Callable[
        [HomeAssistant, ActiveConnection, dict[str, Any], MatterAdapter],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    [HomeAssistant, ActiveConnection, dict[str, Any]], Coroutine[Any, Any, None]
]:
    """Decorate function to get the MatterAdapter."""

    @wraps(func)
    async def _get_matter(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        """Provide the Matter client to the function."""
        matter = get_matter(hass)

        await func(hass, connection, msg, matter)

    return _get_matter


def async_handle_failed_command[**_P](
    func: Callable[
        Concatenate[HomeAssistant, ActiveConnection, dict[str, Any], _P],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    Concatenate[HomeAssistant, ActiveConnection, dict[str, Any], _P],
    Coroutine[Any, Any, None],
]:
    """Decorate function to handle MatterError and send relevant error."""

    @wraps(func)
    async def async_handle_failed_command_func(
        hass: HomeAssistant,
        connection: ActiveConnection,
        msg: dict[str, Any],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        """Handle MatterError within function and send relevant error."""
        try:
            await func(hass, connection, msg, *args, **kwargs)
        except MatterError as err:
            connection.send_error(msg[ID], str(err.error_code), err.args[0])
        except MissingNode as err:
            connection.send_error(msg[ID], ERROR_NODE_NOT_FOUND, err.args[0])
        except ServerVersionTooOld as err:
            connection.send_error(msg[ID], ERR_NOT_SUPPORTED, err.args[0])

    return async_handle_failed_command_func


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
    """Open a commissioning window to commission a device to another."""
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


@callback
def _topology_supported(
    connection: ActiveConnection, msg: dict[str, Any], matter: MatterAdapter
) -> bool:
    """Check if the server supports network topology, send an error if not."""
    server_info = matter.matter_client.server_info
    if server_info is None or server_info.schema_version < TOPOLOGY_SCHEMA_VERSION:
        connection.send_error(
            msg[ID],
            ERR_NOT_SUPPORTED,
            "The Matter server does not support network topology "
            f"(requires schema version {TOPOLOGY_SCHEMA_VERSION}).",
        )
        return False
    return True


@callback
def _serialize_topology(
    hass: HomeAssistant, matter: MatterAdapter, topology: NetworkTopology
) -> dict[str, Any]:
    """Serialize a topology snapshot, annotating nodes with HA device ids."""
    server_info = matter.matter_client.server_info
    dev_reg = dr.async_get(hass)
    result: dict[str, Any] = dataclass_to_dict(topology)
    for node in result["nodes"]:
        device = None
        if (node_id := node.get("node_id")) is not None and server_info is not None:
            device = dev_reg.async_get_device(
                identifiers={get_node_device_identifier(server_info, node_id)}
            )
        node["ha_device_id"] = device.id if device else None
    return result


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/network_topology",
        vol.Optional("refresh", default=False): bool,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
async def websocket_network_topology(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
) -> None:
    """Get the network topology graph."""
    if not _topology_supported(connection, msg, matter):
        return
    topology = await matter.matter_client.get_network_topology(refresh=msg["refresh"])
    connection.send_result(msg[ID], _serialize_topology(hass, matter, topology))


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/subscribe_network_topology",
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
async def websocket_subscribe_network_topology(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
) -> None:
    """Subscribe to network topology updates."""
    if not _topology_supported(connection, msg, matter):
        return

    @callback
    def forward_topology(event: EventType, topology: NetworkTopology) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg[ID], _serialize_topology(hass, matter, topology)
            )
        )

    # the initial fetch also opts this client in to topology events server-side
    topology = await matter.matter_client.get_network_topology()
    connection.subscriptions[msg[ID]] = matter.matter_client.subscribe_events(
        callback=forward_topology,
        event_filter=EventType.NETWORK_TOPOLOGY_UPDATED,
    )
    connection.send_result(msg[ID])
    connection.send_message(
        websocket_api.event_message(
            msg[ID], _serialize_topology(hass, matter, topology)
        )
    )
