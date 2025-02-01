"""DataUpdateCoordinator for pegel_online."""

import logging

from aiopegelonline import CONNECT_ERRORS, PegelOnline, Station, StationMeasurements

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MIN_TIME_BETWEEN_UPDATES

_LOGGER = logging.getLogger(__name__)

type PegelOnlineConfigEntry = ConfigEntry[PegelOnlineDataUpdateCoordinator]


class PegelOnlineDataUpdateCoordinator(DataUpdateCoordinator[StationMeasurements]):
    """DataUpdateCoordinator for the pegel_online integration."""

    config_entry: PegelOnlineConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PegelOnlineConfigEntry,
        api: PegelOnline,
        station: Station,
    ) -> None:
        """Initialize the PegelOnlineDataUpdateCoordinator."""
        self.api = api
        self.station = station
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )

    async def _async_update_data(self) -> StationMeasurements:
        """Fetch data from API endpoint."""
        try:
            return await self.api.async_get_station_measurements(self.station.uuid)
        except CONNECT_ERRORS as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
