"""The NMBS component."""

import asyncio
import logging

from pyrail import iRail
from pyrail.models import StationDetails

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]

type NMBSConfigEntry = ConfigEntry[list[StationDetails]]

NMBS_KEY: HassKey[asyncio.Task[list[StationDetails] | None]] = HassKey(DOMAIN)


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def _async_fetch_stations(hass: HomeAssistant) -> list[StationDetails] | None:
    """Fetch the station list from the iRail API."""
    api_client = iRail(session=async_get_clientsession(hass))
    station_response = await api_client.get_stations()
    if station_response is None:
        return None
    return station_response.stations


async def async_setup_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> bool:
    """Set up NMBS from a config entry."""

    # The station list is shared by all entries and fetched only once. The
    # shared task is stored before any await, so entries that are set up
    # concurrently await the same fetch. A failed fetch is not reused, so a
    # later setup retry fetches again. Raise ConfigEntryNotReady if the API
    # is unavailable so setup is retried instead of failing permanently.
    task = hass.data.get(NMBS_KEY)
    if task is None or (
        task.done()
        and (task.cancelled() or task.exception() is not None or task.result() is None)
    ):
        task = hass.data[NMBS_KEY] = hass.async_create_task(_async_fetch_stations(hass))
    stations = await task
    if stations is None:
        raise ConfigEntryNotReady(
            "Unable to fetch the NMBS station list; the iRail API is unavailable"
        )
    entry.runtime_data = stations

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
