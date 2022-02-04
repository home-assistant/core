"""The PECO Outage Counter integration."""
from __future__ import annotations
from typing import Final

import peco

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import COUNTY_LIST, DOMAIN

PLATFORMS: Final = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PECO Outage Counter from a config entry."""

    if entry.data["county"] not in COUNTY_LIST:
        raise InvalidCountyError(f"{entry.data['county']} is not a valid county")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": peco.PecoOutageApi(),
        "websession": async_get_clientsession(hass),
    }
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class InvalidCountyError(HomeAssistantError):
    """Error to indicate an invalid county."""
