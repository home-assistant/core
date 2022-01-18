"""Provides diagnostics for Z-Wave JS."""
from __future__ import annotations

from zwave_js_server.dump import dump_msgs

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> list[dict]:
    """Return diagnostics for a config entry."""
    msgs: list[dict] = await dump_msgs(
        config_entry.data[CONF_URL], async_get_clientsession(hass)
    )
    return msgs
