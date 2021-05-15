"""The Nobø Ecohub integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pynobo import nobo

from ...const import CONF_IP_ADDRESS
from .const import CONF_SERIAL, DOMAIN

PLATFORMS = ["climate"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nobø Ecohub from a config entry."""

    serial = entry.data.get(CONF_SERIAL)
    ip = entry.data.get(CONF_IP_ADDRESS)
    ip = None if ip == "discover" else ip
    discover = ip is None
    hub = nobo(serial=serial, ip=ip, discover=discover, loop=hass.loop)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = hub

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
