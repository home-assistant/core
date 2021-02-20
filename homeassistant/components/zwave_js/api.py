"""Websocket API for Z-Wave JS."""
import json

from aiohttp import hdrs, web, web_exceptions
import voluptuous as vol
from zwave_js_server import dump

from homeassistant.components import websocket_api
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_CLIENT, DOMAIN, EVENT_DEVICE_ADDED_TO_REGISTRY

ID = "id"
ENTRY_ID = "entry_id"
NODE_ID = "node_id"
TYPE = "type"


@callback
def async_register_api(hass: HomeAssistant) -> None:
    """Register all of our api endpoints."""
    websocket_api.async_register_command(hass, websocket_network_status)
    websocket_api.async_register_command(hass, websocket_node_status)
    websocket_api.async_register_command(hass, websocket_add_node)
    websocket_api.async_register_command(hass, websocket_stop_inclusion)
    websocket_api.async_register_command(hass, websocket_remove_node)
    websocket_api.async_register_command(hass, websocket_stop_exclusion)
    hass.http.register_view(DumpView)  # type: ignore


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required(TYPE): "zwave_js/network_status", vol.Required(ENTRY_ID): str}
)
@callback
def websocket_network_status(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
    """Get the status of the Z-Wave JS network."""
    entry_id = msg[ENTRY_ID]
    client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
    data = {
        "client": {
            "ws_server_url": client.ws_server_url,
            "state": "connected" if client.connected else "disconnected",
            "driver_version": client.version.driver_version,
            "server_version": client.version.server_version,
        },
        "controller": {
            "home_id": client.driver.controller.data["homeId"],
            "nodes": list(client.driver.controller.nodes),
        },
    }
    connection.send_result(
        msg[ID],
        data,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/node_status",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@callback
def websocket_node_status(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
    """Get the status of a Z-Wave JS node."""
    entry_id = msg[ENTRY_ID]
    client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
    node_id = msg[NODE_ID]
    node = client.driver.controller.nodes[node_id]
    data = {
        "node_id": node.node_id,
        "is_routing": node.is_routing,
        "status": node.status,
        "is_secure": node.is_secure,
        "ready": node.ready,
    }
    connection.send_result(
        msg[ID],
        data,
    )


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/add_node",
        vol.Required(ENTRY_ID): str,
        vol.Optional("secure", default=False): bool,
    }
)
async def websocket_add_node(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
    """Add a node to the Z-Wave network."""
    entry_id = msg[ENTRY_ID]
    client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
    controller = client.driver.controller
    include_non_secure = not msg["secure"]

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_event(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(msg[ID], {"event": event["event"]})
        )

    @callback
    def node_added(event: dict) -> None:
        node = event["node"]
        node_details = {
            "node_id": node.node_id,
            "status": node.status,
            "ready": node.ready,
        }
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node added", "node": node_details}
            )
        )

    @callback
    def device_registered(device: DeviceEntry) -> None:
        device_details = {"name": device.name, "id": device.id}
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "device registered", "device": device_details}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    unsubs = [
        controller.on("inclusion started", forward_event),
        controller.on("inclusion failed", forward_event),
        controller.on("inclusion stopped", forward_event),
        controller.on("node added", node_added),
        async_dispatcher_connect(
            hass, EVENT_DEVICE_ADDED_TO_REGISTRY, device_registered
        ),
    ]

    result = await controller.async_begin_inclusion(include_non_secure)
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/stop_inclusion",
        vol.Required(ENTRY_ID): str,
    }
)
async def websocket_stop_inclusion(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
    """Cancel adding a node to the Z-Wave network."""
    entry_id = msg[ENTRY_ID]
    client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
    controller = client.driver.controller
    result = await controller.async_stop_inclusion()
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/stop_exclusion",
        vol.Required(ENTRY_ID): str,
    }
)
async def websocket_stop_exclusion(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
    """Cancel removing a node from the Z-Wave network."""
    entry_id = msg[ENTRY_ID]
    client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
    controller = client.driver.controller
    result = await controller.async_stop_exclusion()
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin  # type:ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/remove_node",
        vol.Required(ENTRY_ID): str,
    }
)
async def websocket_remove_node(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
    """Remove a node from the Z-Wave network."""
    entry_id = msg[ENTRY_ID]
    client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
    controller = client.driver.controller

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_event(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(msg[ID], {"event": event["event"]})
        )

    @callback
    def node_removed(event: dict) -> None:
        node = event["node"]
        node_details = {
            "node_id": node.node_id,
        }

        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node removed", "node": node_details}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    unsubs = [
        controller.on("exclusion started", forward_event),
        controller.on("exclusion failed", forward_event),
        controller.on("exclusion stopped", forward_event),
        controller.on("node removed", node_removed),
    ]

    result = await controller.async_begin_exclusion()
    connection.send_result(
        msg[ID],
        result,
    )


class DumpView(HomeAssistantView):
    """View to dump the state of the Z-Wave JS server."""

    url = "/api/zwave_js/dump/{config_entry_id}"
    name = "api:zwave_js:dump"

    async def get(self, request: web.Request, config_entry_id: str) -> web.Response:
        """Dump the state of Z-Wave."""
        hass = request.app["hass"]

        if config_entry_id not in hass.data[DOMAIN]:
            raise web_exceptions.HTTPBadRequest

        entry = hass.config_entries.async_get_entry(config_entry_id)

        msgs = await dump.dump_msgs(entry.data[CONF_URL], async_get_clientsession(hass))

        return web.Response(
            body=json.dumps(msgs, indent=2) + "\n",
            headers={
                hdrs.CONTENT_TYPE: "application/json",
                hdrs.CONTENT_DISPOSITION: 'attachment; filename="zwave_js_dump.json"',
            },
        )
