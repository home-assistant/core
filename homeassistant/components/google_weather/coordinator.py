"""The Google Weather coordinator."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TypeVar

from google_weather_api import (
    CurrentConditionsResponse,
    DailyForecastResponse,
    GoogleWeatherApi,
    GoogleWeatherApiError,
    HourlyForecastResponse,
)

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)

T = TypeVar(
    "T",
    bound=(
        CurrentConditionsResponse
        | DailyForecastResponse
        | HourlyForecastResponse
        | None
    ),
)


@dataclass
class GoogleWeatherSubEntryRuntimeData:
    """Runtime data for a Google Weather sub-entry."""

    coordinator_observation: GoogleWeatherCurrentConditionsCoordinator
    coordinator_daily_forecast: GoogleWeatherDailyForecastCoordinator
    coordinator_hourly_forecast: GoogleWeatherHourlyForecastCoordinator


@dataclass
class GoogleWeatherRuntimeData:
    """Runtime data for the Google Weather integration."""

    api: GoogleWeatherApi
    subentries_runtime_data: dict[str, GoogleWeatherSubEntryRuntimeData]


type GoogleWeatherConfigEntry = ConfigEntry[GoogleWeatherRuntimeData]


class GoogleWeatherBaseCoordinator(TimestampDataUpdateCoordinator[T]):
    """Base class for Google Weather coordinators."""

    config_entry: GoogleWeatherConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleWeatherConfigEntry,
        subentry: ConfigSubentry,
        data_type_name: str,
        update_interval: timedelta,
        api_method: Callable[..., Awaitable[T]],
    ) -> None:
        """Initialize the data updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Google Weather {data_type_name} coordinator for {subentry.title}",
            update_interval=update_interval,
        )
        self.subentry = subentry
        self._data_type_name = data_type_name
        self._api_method = api_method

    async def _async_update_data(self) -> T:
        """Fetch data from API and handle errors."""
        try:
            return await self._api_method(
                self.subentry.data[CONF_LATITUDE],
                self.subentry.data[CONF_LONGITUDE],
            )
        except GoogleWeatherApiError as err:
            _LOGGER.error(
                "Error fetching %s for %s: %s",
                self._data_type_name,
                self.subentry.title,
                err,
            )
            raise UpdateFailed(f"Error fetching {self._data_type_name}") from err


class GoogleWeatherCurrentConditionsCoordinator(
    GoogleWeatherBaseCoordinator[CurrentConditionsResponse]
):
    """Handle fetching current weather conditions."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleWeatherConfigEntry,
        subentry: ConfigSubentry,
        api: GoogleWeatherApi,
    ) -> None:
        """Initialize the data updater."""
        super().__init__(
            hass,
            config_entry,
            subentry,
            "current weather conditions",
            timedelta(minutes=15),
            api.async_get_current_conditions,
        )


class GoogleWeatherDailyForecastCoordinator(
    GoogleWeatherBaseCoordinator[DailyForecastResponse]
):
    """Handle fetching daily weather forecast."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleWeatherConfigEntry,
        subentry: ConfigSubentry,
        api: GoogleWeatherApi,
    ) -> None:
        """Initialize the data updater."""
        super().__init__(
            hass,
            config_entry,
            subentry,
            "daily weather forecast",
            timedelta(hours=1),
            api.async_get_daily_forecast,
        )


class GoogleWeatherHourlyForecastCoordinator(
    GoogleWeatherBaseCoordinator[HourlyForecastResponse]
):
    """Handle fetching hourly weather forecast."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleWeatherConfigEntry,
        subentry: ConfigSubentry,
        api: GoogleWeatherApi,
    ) -> None:
        """Initialize the data updater."""
        super().__init__(
            hass,
            config_entry,
            subentry,
            "hourly weather forecast",
            timedelta(hours=1),
            api.async_get_hourly_forecast,
        )
