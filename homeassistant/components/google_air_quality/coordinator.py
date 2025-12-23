"""Coordinator for fetching data from Google Air Quality API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Final

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.exceptions import GoogleAirQualityApiError
from google_air_quality_api.model import (
    AirQualityCurrentConditionsData,
    AirQualityForecastData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL: Final = timedelta(hours=1)


@dataclass
class GoogleAirQualitySubEntryRuntimeData:
    """Runtime data for a Google Weather sub-entry."""

    coordinator_current_conditions: GoogleAirQualityCurrentConditionsCoordinator
    coordinators_forecast: dict[int, GoogleAirQualityForecastCoordinator]


@dataclass
class GoogleAirQualityRuntimeData:
    """Runtime data for the Google Air Quality integration."""

    api: GoogleAirQualityApi
    subentries_runtime_data: dict[str, GoogleAirQualitySubEntryRuntimeData]


type GoogleAirQualityConfigEntry = ConfigEntry[GoogleAirQualityRuntimeData]


class GoogleAirQualityCurrentConditionsCoordinator(
    DataUpdateCoordinator[AirQualityCurrentConditionsData]
):
    """Coordinator for fetching Google AirQuality current conditions data."""

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

    async def _async_update_data(self) -> AirQualityCurrentConditionsData:
        """Fetch air quality data for this coordinate."""
        try:
            return await self.client.async_get_current_conditions(self.lat, self.long)
        except GoogleAirQualityApiError as ex:
            _LOGGER.debug("Cannot fetch air quality data: %s", str(ex))
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_fetch",
            ) from ex


class GoogleAirQualityForecastCoordinator(
    DataUpdateCoordinator[AirQualityForecastData]
):
    """Coordinator for fetching Google AirQuality forecast data."""

    config_entry: GoogleAirQualityConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleAirQualityConfigEntry,
        subentry_id: str,
        client: GoogleAirQualityApi,
        hour: int,
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
        self.forecast = hour

    async def _async_update_data(self) -> AirQualityForecastData:
        """Fetch air quality data for this coordinate."""
        try:
            return await self.client.async_get_forecast(
                self.lat, self.long, timedelta(hours=self.forecast)
            )
        except GoogleAirQualityApiError as ex:
            _LOGGER.debug("Cannot fetch air quality data: %s", str(ex))
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_fetch",
            ) from ex
