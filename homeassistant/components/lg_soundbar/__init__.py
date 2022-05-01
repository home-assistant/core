"""The lg_soundbar component."""
import asyncio
import logging

from homeassistant import config_entries, core
from homeassistant.const import Platform

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)
    hass.data[DOMAIN][entry.entry_id] = hass_data

    async def setup_platforms():
        """Set up platforms and initiate connection."""
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_setup(entry, platform)
                for platform in PLATFORMS
            )
        )

    hass.async_create_task(setup_platforms())

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id).cleanup()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
