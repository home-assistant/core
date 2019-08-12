"""Web socket API for Z-Wave."""

import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback

from .const import DATA_NETWORK

_LOGGER = logging.getLogger(__name__)

TYPE = "type"
ID = "id"


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required(TYPE): "zwave/network_status"})
def websocket_network_status(hass, connection, msg):
    """Get Z-Wave network status."""
    network = hass.data[DATA_NETWORK]
    connection.send_result(msg[ID], {"state": network.state})


@callback
def async_load_websocket_api(hass):
    """Set up the web socket API."""
    websocket_api.async_register_command(hass, websocket_network_status)
