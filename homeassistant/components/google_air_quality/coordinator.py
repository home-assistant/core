"""Coordinator for fetching data from Google Air Quality API."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Final

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.exceptions import GoogleAirQualityApiError
from google_air_quality_api.model import AirQualityCurrentConditionsData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CUSTOM_LOCAL_AQI_OPTIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL: Final = timedelta(hours=1)

type GoogleAirQualityConfigEntry = ConfigEntry[GoogleAirQualityRuntimeData]


class GoogleAirQualityUpdateCoordinator(
    DataUpdateCoordinator[AirQualityCurrentConditionsData]
):
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
        subentry = config_entry.subentries[subentry_id]
        self.lat = subentry.data[CONF_LATITUDE]
        self.long = subentry.data[CONF_LONGITUDE]
        self.custom_local_aqi = None
        self.region_code = None
        if subentry.data.get(CUSTOM_LOCAL_AQI_OPTIONS, {}).get("enable_custom_laqi"):
            self.custom_local_aqi = subentry.data[CUSTOM_LOCAL_AQI_OPTIONS][
                "custom_laqi"
            ]
            self.region_code = subentry.data[CUSTOM_LOCAL_AQI_OPTIONS].get("country")

    async def _async_update_data(self) -> AirQualityCurrentConditionsData:
        """Fetch air quality data for this coordinate."""
        try:
            return await self.client.async_get_current_conditions(
                self.lat, self.long, self.region_code, self.custom_local_aqi
            )
        except GoogleAirQualityApiError as ex:
            _LOGGER.debug("Cannot fetch air quality data: %s", str(ex))
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_fetch",
            ) from ex


@dataclass
class GoogleAirQualityRuntimeData:
    """Runtime data for the Google Air Quality integration."""

    api: GoogleAirQualityApi
    subentries_runtime_data: dict[str, GoogleAirQualityUpdateCoordinator]
