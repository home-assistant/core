"""Data update coordinator for the Foreca integration."""

from dataclasses import dataclass
import logging
from typing import override

from pyforeca import (
    CurrentWeather,
    DailyForecast,
    ForecaApiClient,
    ForecaAuthError,
    ForecaError,
    HourlyForecast,
    format_location,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DAILY_PERIODS, DOMAIN, HOURLY_PERIODS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type ForecaConfigEntry = ConfigEntry[ForecaUpdateCoordinator]


@dataclass(slots=True)
class ForecaWeatherData:
    """Weather data returned by the Foreca API."""

    current: CurrentWeather
    hourly: list[HourlyForecast]
    daily: list[DailyForecast]


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
        except ForecaAuthError as err:
            raise ConfigEntryAuthFailed("API key was rejected") from err
        except ForecaError as err:
            raise UpdateFailed(
                f"Error communicating with the Foreca API: {err}"
            ) from err

        return ForecaWeatherData(current=current, hourly=hourly, daily=daily)
