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
    BATTERY_LIMIT_DEFAULT,
    DOMAIN,
    LATITUDE,
    LONGITUDE,
    STATION_ID,
    UPDATE_INTERVAL,
)

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PubliBike integration from a config_old entry."""
    publi_bike = PubliBike()

    station_id = entry.data.get(STATION_ID)
    if station_id:
        all_stations = await hass.async_add_executor_job(publi_bike.getStations)
        station = [s for s in all_stations if s.stationId == station_id][0]
    else:
        location = Location(
            latitude=entry.options.get(LATITUDE, hass.config.latitude),
            longitude=entry.options.get(LONGITUDE, hass.config.longitude),
        )
        station = await hass.async_add_executor_job(
            publi_bike.findNearestStationTo, location
        )

    coordinator = PubliBikeDataUpdateCoordinator(
        hass, station, entry.options.get(BATTERY_LIMIT, BATTERY_LIMIT_DEFAULT)
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update for the PubliBike integration."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class PubliBikeDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator class to manage fetching PubliBike data from single endpoint."""

    def __init__(
        self, hass: HomeAssistant, station: Station, battery_limit: int
    ) -> None:
        """Initialize global PubliBike station data updater."""
        self.station = station
        self.battery_limit = battery_limit
        self.available_ebikes = 0
        self._hass = hass
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{station.stationId}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        """Refresh state of the station."""
        await self._hass.async_add_executor_job(self.station.refresh)
        if self.battery_limit:
            self.available_ebikes = len(
                [
                    bike
                    for bike in self.station.ebikes
                    if bike.batteryLevel >= self.battery_limit
                ]
            )
        else:
            self.available_ebikes = len(self.station.ebikes)
