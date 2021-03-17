"""The Leviosa shades Zone integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["cover"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Leviosa shades Zone component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Leviosa shades Zone from a config entry."""

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
    # if unload_ok:
    #     _LOGGER.debug("data: %s", entry.data)
    #     hass.data[DOMAIN].pop(entry.entry_id)
    #     # hass.data["cover"].pop(entry.entry_id)

    return unload_ok
