"""Coordinator for fetching data from Google Air Quality API."""

import datetime
import logging
from typing import Final

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.exceptions import GoogleAirQualityApiError
from google_air_quality_api.model import AirQualityData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL: Final = datetime.timedelta(hours=1)

type GoogleAirQualityConfigEntry = ConfigEntry[
    dict[str, GoogleAirQualityUpdateCoordinator]
]


class GoogleAirQualityUpdateCoordinator(DataUpdateCoordinator[AirQualityData]):
    """Coordinator for fetching Google AirQuality data."""

    config_entry: GoogleAirQualityConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleAirQualityConfigEntry,
        subentry_id: str,
        client: GoogleAirQualityApi,
    ) -> None:
        """Initialize DataUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{subentry_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.subentry = config_entry.subentries[subentry_id]
        self.subentry_id = subentry_id

    async def _async_update_data(self) -> AirQualityData:
        """Fetch air quality data for this coordinate."""
        latitude = self.subentry.data[CONF_LATITUDE]
        longitude = self.subentry.data[CONF_LONGITUDE]

        try:
            return await self.client.async_air_quality(latitude, longitude)
        except GoogleAirQualityApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_fetch",
                translation_placeholders={"err": str(err)},
            ) from err
