"""DataUpdateCoordinator for pegel_online."""
import logging

from aiopegelonline import CONNECT_ERRORS, PegelOnline, Station, StationMeasurements

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import MIN_TIME_BETWEEN_UPDATES

_LOGGER = logging.getLogger(__name__)


class PegelOnlineDataUpdateCoordinator(DataUpdateCoordinator[StationMeasurements]):
    """DataUpdateCoordinator for the pegel_online integration."""

    def __init__(
        self, hass: HomeAssistant, name: str, api: PegelOnline, station: Station
    ) -> None:
        """Initialize the PegelOnlineDataUpdateCoordinator."""
        self.api = api
        self.station = station
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )

    async def _async_update_data(self) -> StationMeasurements:
        """Fetch data from API endpoint."""
        try:
            return await self.api.async_get_station_measurements(self.station.uuid)
        except CONNECT_ERRORS as err:
            raise UpdateFailed(f"Failed to communicate with API: {err}") from err
