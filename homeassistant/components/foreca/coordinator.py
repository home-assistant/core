"""Data update coordinator for the Foreca integration."""

from dataclasses import dataclass
import logging
from typing import override

from pyforeca import (
    AirQualityDailyForecast,
    AirQualityForecast,
    CurrentWeather,
    DailyForecast,
    ForecaApiClient,
    ForecaAuthError,
    ForecaError,
    HourlyForecast,
    MinutelyForecast,
    Observation,
    UsageMonth,
    format_location,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DAILY_PERIODS, DOMAIN, HOURLY_PERIODS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type ForecaConfigEntry = ConfigEntry[ForecaUpdateCoordinator]


@dataclass(slots=True)
class ForecaWeatherData:
    """Weather and air quality data returned by the Foreca API."""

    current: CurrentWeather
    hourly: list[HourlyForecast]
    daily: list[DailyForecast]
    air_quality: AirQualityForecast | None
    air_quality_daily: list[AirQualityDailyForecast]
    observation: Observation | None
    minutely: list[MinutelyForecast]
    usage: UsageMonth | None


class ForecaUpdateCoordinator(DataUpdateCoordinator[ForecaWeatherData]):
    """Class to manage fetching Foreca data."""

    config_entry: ForecaConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ForecaConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.client = ForecaApiClient(
            entry.data[CONF_API_KEY], session=async_get_clientsession(hass)
        )
        self.location = format_location(
            lon=entry.data[CONF_LONGITUDE], lat=entry.data[CONF_LATITUDE]
        )
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Foreca",
            entry_type=DeviceEntryType.SERVICE,
        )

    @override
    async def _async_update_data(self) -> ForecaWeatherData:
        """Fetch data from the Foreca API."""
        try:
            current = await self.client.current(self.location)
            hourly = await self.client.forecast_hourly(
                self.location, periods=HOURLY_PERIODS, dataset="full"
            )
            daily = await self.client.forecast_daily(
                self.location, periods=DAILY_PERIODS, dataset="full"
            )
            observation = await self.client.observation_latest(self.location)
            minutely = await self.client.forecast_minutely(self.location)
        except ForecaAuthError as err:
            raise ConfigEntryAuthFailed("API key was rejected") from err
        except ForecaError as err:
            raise UpdateFailed(
                f"Error communicating with the Foreca API: {err}"
            ) from err

        # Air quality must never fail the weather update: it is a separate
        # product on the account and can be missing from the plan.
        air_quality: AirQualityForecast | None = None
        air_quality_daily: list[AirQualityDailyForecast] = []
        try:
            aq_forecast = await self.client.air_quality_hourly(self.location, periods=1)
            air_quality = aq_forecast[0] if aq_forecast else None
            air_quality_daily = await self.client.air_quality_daily(
                self.location, periods=4
            )
        except ForecaAuthError as err:
            raise ConfigEntryAuthFailed("API key was rejected") from err
        except ForecaError as err:
            _LOGGER.warning("Air quality data unavailable: %s", err)

        # Usage counts are account telemetry, not weather: never fail the update.
        usage: UsageMonth | None = None
        try:
            usage = await self.client.usage_month(dt_util.utcnow().strftime("%Y-%m"))
        except ForecaError as err:
            _LOGGER.debug("Usage counts unavailable: %s", err)

        return ForecaWeatherData(
            current=current,
            hourly=hourly,
            daily=daily,
            air_quality=air_quality,
            air_quality_daily=air_quality_daily,
            observation=observation,
            minutely=minutely,
            usage=usage,
        )
