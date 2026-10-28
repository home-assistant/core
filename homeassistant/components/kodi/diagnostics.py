"""Diagnostics support for Kodi."""

from typing import Any

from jsonrpc_base.jsonrpc import ProtocolError, TransportError

from homeassistant.const import CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant

from . import KodiConfigEntry
from .const import CONF_WS_PORT


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: KodiConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    connection = entry.runtime_data.connection
    kodi = entry.runtime_data.kodi
    diagnostics: dict[str, Any] = {
        "config": {
            CONF_PORT: entry.data[CONF_PORT],
            CONF_WS_PORT: entry.data[CONF_WS_PORT],
            CONF_SSL: entry.data[CONF_SSL],
        },
        "connection": {
            "connected": connection.connected,
            "websocket": connection.can_subscribe,
        },
    }
    if not connection.connected:
        return diagnostics
    try:
        properties = await kodi.get_application_properties(["version"])
        players = await kodi.get_players()
    except (TransportError, ProtocolError) as error:
        diagnostics["error"] = str(error)
        return diagnostics
    diagnostics["version"] = properties["version"]
    diagnostics["active_players"] = players
    return diagnostics
