"""The pioneer component."""
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import HomeAssistant

from .const import CONF_SOURCES, DOMAIN
from .media_player import PioneerDevice

PLATFORMS = ["media_player"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Pioneer component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Pioneer AVR from a config entry."""
    device = PioneerDevice(
        name=entry.data[CONF_NAME],
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        timeout=entry.data[CONF_TIMEOUT],
        sources=entry.data[CONF_SOURCES],
        unique_id=entry.unique_id,
    )

    hass.data[DOMAIN][entry.entry_id] = device

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
