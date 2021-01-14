"""Websocket API for Z-Wave JS."""

import logging
from typing import Dict

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


# Decorator causes typing error from mypy, ignoring locally until it is
# fixed in the core websocket_api class
@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required(TYPE): "zwave_js/network_status", vol.Required(ENTRY_ID): str}
)
async def websocket_network_status(
    hass: HomeAssistant, connection: ActiveConnection, msg: Dict
) -> None:
    """Get the status of the Z-Wave JS network."""
    entry_id = msg[ENTRY_ID]
    client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
    data = {
        "client": {
            "ws_server_url": client.ws_server_url,
            "state": client.state,
            "version": client.version.__dict__,
        },
        "controller": client.driver.controller.data,
    }
    connection.send_result(
        msg[ID],
        data,
    )
