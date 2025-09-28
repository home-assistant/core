"""The met_eireann component."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any, Self

import meteireann

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=60)


class MetEireannWeatherData:
    """Keep data for Met Éireann weather entities."""

    def __init__(
        self, config: Mapping[str, Any], weather_data: meteireann.WeatherData
    ) -> None:
        """Initialise the weather entity data."""
        self._config = config
        self._weather_data = weather_data
        self.current_weather_data: dict[str, Any] = {}
        self.daily_forecast: list[dict[str, Any]] = []
        self.hourly_forecast: list[dict[str, Any]] = []

    async def fetch_data(self) -> Self:
        """Fetch data from API - (current weather and forecast)."""
        await self._weather_data.fetching_data()
        self.current_weather_data = self._weather_data.get_current_weather()
        time_zone = dt_util.get_default_time_zone()
        self.daily_forecast = self._weather_data.get_forecast(time_zone, False)
        self.hourly_forecast = self._weather_data.get_forecast(time_zone, True)
        return self


class MetEireannUpdateCoordinator(DataUpdateCoordinator[MetEireannWeatherData]):
    """Coordinator for Met Éireann weather data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        raw_weather_data = meteireann.WeatherData(
            async_get_clientsession(hass),
            latitude=config_entry.data[CONF_LATITUDE],
            longitude=config_entry.data[CONF_LONGITUDE],
            altitude=config_entry.data[CONF_ELEVATION],
        )
        self._weather_data = MetEireannWeatherData(config_entry.data, raw_weather_data)

    async def _async_update_data(self) -> MetEireannWeatherData:
        """Fetch data from Met Éireann."""
        try:
            return await self._weather_data.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
