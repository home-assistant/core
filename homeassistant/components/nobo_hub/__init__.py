"""The Nobø Ecohub integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pynobo import nobo

from ...const import CONF_IP_ADDRESS
from .const import CONF_SERIAL, DOMAIN, HUB, UNSUBSCRIBE

PLATFORMS = ["climate"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nobø Ecohub from a config entry."""

    serial = entry.data.get(CONF_SERIAL)
    ip = entry.data.get(CONF_IP_ADDRESS)
    name = entry.title
    discover = ip is None
    hub = nobo(serial=serial, ip=ip, discover=discover, loop=hass.loop)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {HUB: hub}

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    unsubscribe = entry.add_update_listener(options_update_listener)
    hass.data[DOMAIN][entry.entry_id][UNSUBSCRIBE] = unsubscribe

    _LOGGER.info("component '%s' is up and running on %s:%s", name, ip, serial)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    hub = hass.data[DOMAIN][entry.entry_id][HUB]
    serial = entry.data.get(CONF_SERIAL)
    ip = entry.data.get(CONF_IP_ADDRESS)
    name = entry.title
    await hub.stop()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][entry.entry_id][UNSUBSCRIBE]()
        hass.data[DOMAIN].pop(entry.entry_id)

    _LOGGER.info("component '%s' on %s:%s is stopped", name, ip, serial)

    return unload_ok


async def options_update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
