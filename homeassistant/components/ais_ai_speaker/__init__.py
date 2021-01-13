"""The AI Speaker integration."""
import asyncio

from aisapi.ws import AisWebService

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

PLATFORMS = ["sensor", "media_player"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the AI Speaker integration."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up AI Speaker from a config entry."""
    web_session = aiohttp_client.async_get_clientsession(hass)
    ais = AisWebService(hass.loop, web_session, entry.data["host"])
    hass.data[DOMAIN][entry.entry_id] = ais

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
