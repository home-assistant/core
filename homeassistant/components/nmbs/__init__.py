"""The NMBS component."""

import logging

from pyrail import IRail, PyRailError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    NMBS_STATION_DATA,
    PLATFORMS,
    STATION_CACHE_DURATION,
    NMBSStationCache,
)
from .coordinator import NMBSConfigEntry, NMBSCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> None:
    """Set up NMBS from a config entry."""

    station_cache = hass.data.get(NMBS_STATION_DATA)
    if station_cache is None or (
        dt_util.utcnow() - station_cache.fetched_at >= STATION_CACHE_DURATION
    ):
        api_client = IRail(session=async_get_clientsession(hass))
        try:
            station_response = await api_client.get_stations()
        except (PyRailError, TimeoutError, ValueError, LookupError) as err:
            if station_cache is None:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="station_list_unavailable",
                ) from err
            _LOGGER.warning("Unable to refresh the NMBS station list: %s", err)
        else:
            if station_response is not None:
                station_cache = NMBSStationCache(
                    station_response.stations, dt_util.utcnow()
                )
            elif station_cache is None:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="station_list_unavailable",
                )
            hass.data[NMBS_STATION_DATA] = station_cache

    coordinator = NMBSCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
