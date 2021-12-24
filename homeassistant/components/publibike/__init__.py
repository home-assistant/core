"""The PubliBike Public API integration."""

import logging

from pypublibike.location import Location
from pypublibike.publibike import PubliBike
from pypublibike.station import Station

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BATTERY_LIMIT,
    DOMAIN,
    LATITUDE,
    LONGITUDE,
    STATION_ID,
    UPDATE_INTERVAL,
)

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PubliBike integration from a config entry."""

    publi_bike = PubliBike()

    station_id = entry.data.get(STATION_ID)
    if station_id:
        all_stations = await hass.async_add_executor_job(publi_bike.getStations)
        station = [s for s in all_stations if s.stationId == station_id][0]
    else:
        lat = (
            entry.data[LATITUDE]
            if LATITUDE in entry.data.keys()
            else hass.config.latitude
        )
        lon = (
            entry.data[LONGITUDE]
            if LONGITUDE in entry.data.keys()
            else hass.config.longitude
        )
        location = Location(latitude=lat, longitude=lon)
        station = await hass.async_add_executor_job(
            publi_bike.findNearestStationTo, location
        )

    coordinator = PubliBikeDataUpdateCoordinator(hass, station)

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "station": station,
        BATTERY_LIMIT: entry.data[BATTERY_LIMIT],
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


class PubliBikeDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator class to manage fetching PubliBike data from single endpoint."""

    def __init__(self, hass: HomeAssistant, station: Station) -> None:
        """Initialize global PubliBike station data updater."""
        self._station = station
        self._hass = hass
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{station.stationId}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        """Refresh state of the station."""
        await self._hass.async_add_executor_job(self._station.refresh)
