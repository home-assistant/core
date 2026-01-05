"""The AccuWeather coordinator."""

from __future__ import annotations

from asyncio import timeout
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from accuweather import AccuWeather, ApiError, InvalidApiKeyError, RequestsExceededError
from aiohttp.client_exceptions import ClientConnectorError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    MANUFACTURER,
    UPDATE_INTERVAL_DAILY_FORECAST,
    UPDATE_INTERVAL_HOURLY_FORECAST,
    UPDATE_INTERVAL_OBSERVATION,
)

EXCEPTIONS = (ApiError, ClientConnectorError, RequestsExceededError)

_LOGGER = logging.getLogger(__name__)


@dataclass
class AccuWeatherData:
    """Data for AccuWeather integration."""

    coordinator_observation: AccuWeatherObservationDataUpdateCoordinator
    coordinator_daily_forecast: AccuWeatherDailyForecastDataUpdateCoordinator
    coordinator_hourly_forecast: AccuWeatherHourlyForecastDataUpdateCoordinator


type AccuWeatherConfigEntry = ConfigEntry[AccuWeatherData]


class AccuWeatherObservationDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, Any]]
):
    """Class to manage fetching AccuWeather data API."""

    config_entry: AccuWeatherConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AccuWeatherConfigEntry,
        accuweather: AccuWeather,
    ) -> None:
        """Initialize."""
        self.accuweather = accuweather
        self.location_key = accuweather.location_key
        name = config_entry.data[CONF_NAME]

        if TYPE_CHECKING:
            assert self.location_key is not None

        self.device_info = _get_device_info(self.location_key, name)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{name} (observation)",
            update_interval=UPDATE_INTERVAL_OBSERVATION,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            async with timeout(10):
                result = await self.accuweather.async_get_current_conditions()
        except EXCEPTIONS as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="current_conditions_update_error",
                translation_placeholders={"error": repr(error)},
            ) from error
        except InvalidApiKeyError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={"entry": self.config_entry.title},
            ) from err

        _LOGGER.debug("Requests remaining: %d", self.accuweather.requests_remaining)

        return result


class AccuWeatherForecastDataUpdateCoordinator(
    TimestampDataUpdateCoordinator[list[dict[str, Any]]]
):
    """Base class for AccuWeather forecast."""

    config_entry: AccuWeatherConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AccuWeatherConfigEntry,
        accuweather: AccuWeather,
        coordinator_type: str,
        update_interval: timedelta,
        fetch_method: Callable[..., Awaitable[list[dict[str, Any]]]],
    ) -> None:
        """Initialize."""
        self.accuweather = accuweather
        self.location_key = accuweather.location_key
        self._fetch_method = fetch_method
        name = config_entry.data[CONF_NAME]

        if TYPE_CHECKING:
            assert self.location_key is not None

        self.device_info = _get_device_info(self.location_key, name)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{name} ({coordinator_type})",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Update forecast data via library."""
        try:
            async with timeout(10):
                result = await self._fetch_method(language=self.hass.config.language)
        except EXCEPTIONS as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="forecast_update_error",
                translation_placeholders={"error": repr(error)},
            ) from error
        except InvalidApiKeyError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={"entry": self.config_entry.title},
            ) from err

        _LOGGER.debug("Requests remaining: %d", self.accuweather.requests_remaining)
        return result


class AccuWeatherDailyForecastDataUpdateCoordinator(
    AccuWeatherForecastDataUpdateCoordinator
):
    """Coordinator for daily forecast."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AccuWeatherConfigEntry,
        accuweather: AccuWeather,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            config_entry,
            accuweather,
            "daily forecast",
            UPDATE_INTERVAL_DAILY_FORECAST,
            fetch_method=accuweather.async_get_daily_forecast,
        )


class AccuWeatherHourlyForecastDataUpdateCoordinator(
    AccuWeatherForecastDataUpdateCoordinator
):
    """Coordinator for hourly forecast."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AccuWeatherConfigEntry,
        accuweather: AccuWeather,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            config_entry,
            accuweather,
            "hourly forecast",
            UPDATE_INTERVAL_HOURLY_FORECAST,
            fetch_method=accuweather.async_get_hourly_forecast,
        )


def _get_device_info(location_key: str, name: str) -> DeviceInfo:
    """Get device info."""
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, location_key)},
        manufacturer=MANUFACTURER,
        name=name,
        # You don't need to provide specific details for the URL,
        # so passing in _ characters is fine if the location key
        # is correct
        configuration_url=(
            "http://accuweather.com/en/"
            f"_/_/{location_key}/weather-forecast/{location_key}/"
        ),
    )
