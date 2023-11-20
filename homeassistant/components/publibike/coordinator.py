"""Support for PubliBike Public API for bike sharing in Switzerland."""

import logging

from pypublibike.station import Station

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, UPDATE_INTERVAL

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


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
