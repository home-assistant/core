"""The aurora component."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp import ClientError
from auroranoaa import AuroraForecast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class AuroraDataUpdateCoordinator(DataUpdateCoordinator[int]):
    """Class to manage fetching data from the NOAA Aurora API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: AuroraForecast,
        latitude: float,
        longitude: float,
        threshold: float,
    ) -> None:
        """Initialize the data updater."""

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="Aurora",
            update_interval=timedelta(minutes=5),
        )

        self.api = api
        self.latitude = int(latitude)
        self.longitude = int(longitude)
        self.threshold = int(threshold)

    async def _async_update_data(self) -> int:
        """Fetch the data from the NOAA Aurora Forecast."""

        try:
            return await self.api.get_forecast_data(self.longitude, self.latitude)
        except ClientError as error:
            raise UpdateFailed(f"Error updating from NOAA: {error}") from error
