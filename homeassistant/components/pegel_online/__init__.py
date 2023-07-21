"""The pegel_online component."""
from __future__ import annotations

import logging

from aiopegelonline import CONNECT_ERRORS, PegelOnline

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_STATION,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
)
from .model import PegelOnlineData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up pegel_online entry."""
    station_uuid = entry.data[CONF_STATION]
    name = entry.title

    _LOGGER.debug("Setting up station with uuid %s", station_uuid)

    api = PegelOnline(async_get_clientsession(hass))
    station = await api.async_get_station_details(station_uuid)

    async def async_update_data() -> PegelOnlineData:
        """Fetch data from API endpoint."""
        try:
            current_measurement = await api.async_get_station_measurement(station_uuid)
        except CONNECT_ERRORS as err:
            raise UpdateFailed(f"Failed to communicate with API: {err}") from err

        return {"current_measurement": current_measurement}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = (coordinator, station)

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload pegel_online entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
