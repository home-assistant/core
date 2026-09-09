"""Websocket API exposing the Modbus connections the integration keeps open."""

from typing import Any, Final

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .connection import async_get_connection_info

TYPE_LIST_CONNECTIONS: Final = "modbus/connections/list"


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register the Modbus websocket commands."""
    websocket_api.async_register_command(hass, websocket_list_connections)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): TYPE_LIST_CONNECTIONS})
@callback
def websocket_list_connections(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List the connections, and which config entries hold units on each."""
    connection.send_result(
        msg["id"],
        {
            "connections": [
                {
                    "endpoint": list(info.endpoint),
                    "connected": info.connected,
                    "units": info.units,
                }
                for info in async_get_connection_info(hass)
            ]
        },
    )
