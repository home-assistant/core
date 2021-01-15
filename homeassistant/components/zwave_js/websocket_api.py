"""Websocket API for Z-Wave JS."""

import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import HomeAssistant, callback

from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)

ID = "id"
ENTRY_ID = "entry_id"
TYPE = "type"


@callback
def async_register_api(hass: HomeAssistant) -> None:
    """Register all of our api endpoints."""
    websocket_api.async_register_command(hass, websocket_network_status)


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
            "state": client.state,
            "driver_version": client.version.driver_version,
            "server_version": client.version.server_version,
        },
        "controller": {
            "home_id": client.driver.controller.data["homeId"],
            "node_count": len(client.driver.controller.nodes),
        },
    }
    connection.send_result(
        msg[ID],
        data,
    )
