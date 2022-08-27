"""The Ecowitt Weather Station Component."""
from __future__ import annotations

from aioecowitt import EcoWittListener

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .const import CONF_PATH, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Ecowitt component from UI."""
    hass.data.setdefault(DOMAIN, {})

    ecowitt = hass.data[DOMAIN][entry.entry_id] = EcoWittListener(
        port=entry.data[CONF_PORT], path=entry.data[CONF_PATH]
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    await ecowitt.start()

    # Close on shutdown
    async def _stop_ecowitt(_: Event):
        """Stop the Ecowitt listener."""
        await ecowitt.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_ecowitt)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    ecowitt = hass.data[DOMAIN][entry.entry_id]
    await ecowitt.stop()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
