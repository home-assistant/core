"""The NMBS component."""

import logging

from pyrail import iRail
from pyrail.models import StationDetails

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.singleton import singleton
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]

type NMBSConfigEntry = ConfigEntry[list[StationDetails]]

NMBS_KEY: HassKey[list[StationDetails]] = HassKey(DOMAIN)


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@singleton(NMBS_KEY, async_=True)
async def _async_get_stations(hass: HomeAssistant) -> list[StationDetails]:
    """Fetch the station list, which is shared by all entries."""
    api_client = iRail(session=async_get_clientsession(hass))
    station_response = await api_client.get_stations()
    if station_response is None:
        raise ConfigEntryNotReady(
            "Unable to fetch the NMBS station list; the iRail API is unavailable"
        )
    return station_response.stations


async def async_setup_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> bool:
    """Set up NMBS from a config entry."""
    entry.runtime_data = await _async_get_stations(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
