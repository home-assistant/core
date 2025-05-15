"""Coordinator for fetching data from Google Air Quality API."""

import datetime
import logging
from typing import Final

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.exceptions import GooglePhotosApiError
from google_air_quality_api.model import AirQualityData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL: Final = datetime.timedelta(hours=1)
ALBUM_PAGE_SIZE = 50

type GoogleAirQualityConfigEntry = ConfigEntry[GoogleAirQualityUpdateCoordinator]


class GoogleAirQualityUpdateCoordinator(DataUpdateCoordinator[AirQualityData]):
    """Coordinator for fetching Google AirQuality data."""

    config_entry: GoogleAirQualityConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleAirQualityConfigEntry,
        client: GoogleAirQualityApi,
    ) -> None:
        """Initialize DataUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            update_method=self._async_update_data,
        )
        self.client = client
        self.config_entry = config_entry

    async def _async_update_data(self) -> AirQualityData:
        """Fetch albums from API endpoint."""
        try:
            return await self.client.async_air_quality(
                self.config_entry.data[CONF_LATITUDE],
                self.config_entry.data[CONF_LONGITUDE],
            )
        except GooglePhotosApiError as err:
            _LOGGER.debug("Error listing air qulaity: %s", err)
            raise UpdateFailed(f"Error listing albums: {err}") from err
