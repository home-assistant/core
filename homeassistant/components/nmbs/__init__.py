"""The NMBS component."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

import logging

from pyrail import iRail

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NMBS from a config entry."""

    # The station list is shared by all entries, so fetch and cache it only
    # once. Raise ConfigEntryNotReady if the API is unavailable so setup is
    # retried instead of failing permanently.
    if not hass.data.get(DOMAIN):
        api_client = iRail(session=async_get_clientsession(hass))
        station_response = await api_client.get_stations()
        if station_response is None:
            raise ConfigEntryNotReady(
                "Unable to fetch the NMBS station list; the iRail API is unavailable"
            )
        hass.data[DOMAIN] = station_response.stations

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
