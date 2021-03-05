"""Zerproc lights integration."""
import asyncio

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = ["light"]


async def async_setup(hass, config):
    """Set up the Zerproc platform."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT})
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Zerproc from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if "addresses" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["addresses"] = set()

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data.pop(DOMAIN, None)
    return all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
