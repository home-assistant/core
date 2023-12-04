"""The Nobø Ecohub integration."""
from __future__ import annotations

from pynobo import nobo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_AUTO_DISCOVERED, CONF_SERIAL, DOMAIN

PLATFORMS = [Platform.CLIMATE, Platform.SELECT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nobø Ecohub from a config entry."""

    serial = entry.data[CONF_SERIAL]
    discover = entry.data[CONF_AUTO_DISCOVERED]
    ip_address = None if discover else entry.data[CONF_IP_ADDRESS]
    hub = nobo(serial=serial, ip=ip_address, discover=discover, synchronous=False)
    await hub.connect()

    hass.data.setdefault(DOMAIN, {})

    async def _async_close(event):
        """Close the Nobø Ecohub socket connection when HA stops."""
        await hub.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close)
    )
    hass.data[DOMAIN][entry.entry_id] = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    await hub.start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    hub: nobo = hass.data[DOMAIN][entry.entry_id]
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hub.stop()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def options_update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
