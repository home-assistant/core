"""The Google Weather coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from google_weather_api import GoogleWeatherApi, GoogleWeatherApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class GoogleWeatherRuntimeData:
    """Runtime data for the Google Weather integration."""

    coordinator_observation: GoogleWeatherCurrentConditionsCoordinator
    coordinator_daily_forecast: GoogleWeatherDailyForecastCoordinator
    coordinator_hourly_forecast: GoogleWeatherHourlyForecastCoordinator


type GoogleWeatherConfigEntry = ConfigEntry[GoogleWeatherRuntimeData]


class GoogleWeatherCurrentConditionsCoordinator(
    TimestampDataUpdateCoordinator[dict[str, Any]]
):
    """Handle fetching current weather conditions."""

    config_entry: GoogleWeatherConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleWeatherConfigEntry,
        api: GoogleWeatherApi,
    ) -> None:
        """Initialize the data updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Google Weather current conditions coordinator for {config_entry.title}",
            update_interval=timedelta(minutes=15),
        )
        self.api = api
        assert config_entry.unique_id
        self.device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(config_entry.domain, config_entry.unique_id)},
            manufacturer="Google",
            name=config_entry.title,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch current weather conditions."""
        try:
            return await self.api.async_get_current_conditions()
        except GoogleWeatherApiError as err:
            _LOGGER.error("Error fetching current weather conditions: %s", err)
            raise UpdateFailed from err


class GoogleWeatherDailyForecastCoordinator(
    TimestampDataUpdateCoordinator[dict[str, Any]]
):
    """Handle fetching daily weather forecast."""

    config_entry: GoogleWeatherConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleWeatherConfigEntry,
        api: GoogleWeatherApi,
    ) -> None:
        """Initialize the data updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Google Weather daily forecast coordinator for {config_entry.title}",
            update_interval=timedelta(hours=1),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch daily weather forecast."""
        try:
            return await self.api.async_get_daily_forecast()
        except GoogleWeatherApiError as err:
            _LOGGER.error("Error fetching daily weather forecast: %s", err)
            raise UpdateFailed from err


class GoogleWeatherHourlyForecastCoordinator(
    TimestampDataUpdateCoordinator[dict[str, Any]]
):
    """Handle fetching hourly weather forecast."""

    config_entry: GoogleWeatherConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleWeatherConfigEntry,
        api: GoogleWeatherApi,
    ) -> None:
        """Initialize the data updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Google Weather hourly forecast coordinator for {config_entry.title}",
            update_interval=timedelta(hours=1),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch hourly weather forecast."""
        try:
            return await self.api.async_get_hourly_forecast()
        except GoogleWeatherApiError as err:
            _LOGGER.error("Error fetching hourly weather forecast: %s", err)
            raise UpdateFailed from err
