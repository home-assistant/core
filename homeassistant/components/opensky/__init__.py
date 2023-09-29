"""The opensky component."""
from __future__ import annotations

from python_opensky import OpenSky

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT, DOMAIN, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up opensky from a config entry."""

    client = OpenSky(session=async_get_clientsession(hass))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {CLIENT: client}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload opensky config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
