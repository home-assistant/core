"""The aurora component."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from aiohttp import ClientError
from auroranoaa import AuroraForecast

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_THRESHOLD, DEFAULT_THRESHOLD

if TYPE_CHECKING:
    from . import AuroraConfigEntry

_LOGGER = logging.getLogger(__name__)


class AuroraDataUpdateCoordinator(DataUpdateCoordinator[int]):
    """Class to manage fetching data from the NOAA Aurora API."""

    config_entry: AuroraConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the data updater."""

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="Aurora",
            update_interval=timedelta(minutes=5),
        )

        self.api = AuroraForecast(async_get_clientsession(hass))
        self.latitude = int(self.config_entry.data[CONF_LATITUDE])
        self.longitude = int(self.config_entry.data[CONF_LONGITUDE])
        self.threshold = int(
            self.config_entry.options.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)
        )

    async def _async_update_data(self) -> int:
        """Fetch the data from the NOAA Aurora Forecast."""

        try:
            return await self.api.get_forecast_data(self.longitude, self.latitude)
        except ClientError as error:
            raise UpdateFailed(f"Error updating from NOAA: {error}") from error
