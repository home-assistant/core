"""Support for Meteoclimatic weather data."""

import logging

from meteoclimatic import MeteoclimaticClient, Observation
from meteoclimatic.exceptions import MeteoclimaticError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_STATION_CODE, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type MeteoclimaticConfigEntry = ConfigEntry[MeteoclimaticUpdateCoordinator]


class MeteoclimaticUpdateCoordinator(DataUpdateCoordinator[Observation]):
    """Coordinator for Meteoclimatic weather data."""

    config_entry: MeteoclimaticConfigEntry

    def __init__(self, hass: HomeAssistant, entry: MeteoclimaticConfigEntry) -> None:
        """Initialize the coordinator."""
        self._station_code = entry.data[CONF_STATION_CODE]
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"Meteoclimatic weather for {entry.title} ({self._station_code})",
            update_interval=SCAN_INTERVAL,
        )
        self._meteoclimatic_client = MeteoclimaticClient()

    async def _async_update_data(self) -> Observation:
        """Obtain the latest data from Meteoclimatic."""
        try:
            return await self.hass.async_add_executor_job(
                self._meteoclimatic_client.weather_at_station, self._station_code
            )
        except MeteoclimaticError as err:
            raise UpdateFailed(f"Error while retrieving data: {err}") from err
