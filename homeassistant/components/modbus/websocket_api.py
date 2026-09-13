"""Websocket API exposing the Modbus connections the integration keeps open."""

from typing import Any, Final

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .connection import async_get_connection_info
from .const import DATA_MODBUS_HUBS

TYPE_LIST_CONNECTIONS: Final = "modbus/connections/list"

SOURCE_CONFIG_ENTRY: Final = "config_entry"
SOURCE_YAML: Final = "yaml"


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
    """List the connections held over config entries, then those from YAML.

    The unit ids of a connection are keyed by config entry id, or by hub name
    for one from YAML. A YAML hub is a link of its own rather than a hold on a
    shared connection, so it is listed separately even when it addresses a
    device a config entry also talks to.
    """
    connection.send_result(
        msg["id"],
        {
            "connections": [
                {
                    "endpoint": list(info.endpoint),
                    "connected": info.connected,
                    "source": SOURCE_CONFIG_ENTRY,
                    "units": info.units,
                }
                for info in async_get_connection_info(hass)
            ]
            + [
                {
                    "endpoint": list(hub.endpoint),
                    "connected": hub.connected,
                    "source": SOURCE_YAML,
                    "units": {name: hub.units},
                }
                for name, hub in hass.data.get(DATA_MODBUS_HUBS, {}).items()
            ]
        },
    )
