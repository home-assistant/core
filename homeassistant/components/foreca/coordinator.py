"""Data update coordinator for the Foreca integration."""

from dataclasses import dataclass
import logging
from typing import override

from pyforeca import (
    CurrentWeather,
    DailyForecast,
    ForecaApiClient,
    ForecaError,
    HourlyForecast,
    format_location,
)

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DAILY_PERIODS, DOMAIN, HOURLY_PERIODS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type ForecaConfigEntry = ConfigEntry[dict[str, ForecaUpdateCoordinator]]


@dataclass(slots=True)
class ForecaWeatherData:
    """Weather data returned by the Foreca API."""

    current: CurrentWeather
    hourly: list[HourlyForecast]
    daily: list[DailyForecast]


class ForecaUpdateCoordinator(DataUpdateCoordinator[ForecaWeatherData]):
    """Class to manage fetching Foreca data for one location."""

    config_entry: ForecaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ForecaConfigEntry,
        subentry: ConfigSubentry,
        client: ForecaApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {subentry.title}",
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.client = client
        self.location = format_location(
            lon=subentry.data[CONF_LONGITUDE], lat=subentry.data[CONF_LATITUDE]
        )
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
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
        except ForecaError as err:
            raise UpdateFailed(
                f"Error communicating with the Foreca API: {err}"
            ) from err

        return ForecaWeatherData(current=current, hourly=hourly, daily=daily)
