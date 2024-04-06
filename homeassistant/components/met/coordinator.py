"""DataUpdateCoordinator for Met.no integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from random import randrange
from types import MappingProxyType
from typing import Any, Self

import metno

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    EVENT_CORE_CONFIG_UPDATE,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_TRACK_HOME, DOMAIN

# Dedicated Home Assistant endpoint - do not change!
URL = "https://aa015h6buqvih86i1.api.met.no/weatherapi/locationforecast/2.0/complete"

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Unable to connect to the web site."""


class MetWeatherData:
    """Keep data for Met.no weather entities."""

    def __init__(self, hass: HomeAssistant, config: MappingProxyType[str, Any]) -> None:
        """Initialise the weather entity data."""
        self.hass = hass
        self._config = config
        self._weather_data: metno.MetWeatherData
        self.current_weather_data: dict = {}
        self.daily_forecast: list[dict] = []
        self.hourly_forecast: list[dict] = []
        self._coordinates: dict[str, str] | None = None

    def set_coordinates(self) -> bool:
        """Weather data initialization - set the coordinates."""
        if self._config.get(CONF_TRACK_HOME, False):
            latitude = self.hass.config.latitude
            longitude = self.hass.config.longitude
            elevation = self.hass.config.elevation
        else:
            latitude = self._config[CONF_LATITUDE]
            longitude = self._config[CONF_LONGITUDE]
            elevation = self._config[CONF_ELEVATION]

        coordinates = {
            "lat": str(latitude),
            "lon": str(longitude),
            "msl": str(elevation),
        }
        if coordinates == self._coordinates:
            return False
        self._coordinates = coordinates

        self._weather_data = metno.MetWeatherData(
            coordinates, async_get_clientsession(self.hass), api_url=URL
        )
        return True

    async def fetch_data(self) -> Self:
        """Fetch data from API - (current weather and forecast)."""
        resp = await self._weather_data.fetching_data()
        if not resp:
            raise CannotConnect
        self.current_weather_data = self._weather_data.get_current_weather()
        time_zone = dt_util.DEFAULT_TIME_ZONE
        self.daily_forecast = self._weather_data.get_forecast(time_zone, False, 0)
        self.hourly_forecast = self._weather_data.get_forecast(time_zone, True)
        return self


class MetDataUpdateCoordinator(DataUpdateCoordinator[MetWeatherData]):
    """Class to manage fetching Met data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize global Met data updater."""
        self._unsub_track_home: Callable[[], None] | None = None
        self.weather = MetWeatherData(hass, config_entry.data)
        self.weather.set_coordinates()

        update_interval = timedelta(minutes=randrange(55, 65))

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> MetWeatherData:
        """Fetch data from Met."""
        try:
            return await self.weather.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err

    def track_home(self) -> None:
        """Start tracking changes to HA home setting."""
        if self._unsub_track_home:
            return

        async def _async_update_weather_data(_event: Event | None = None) -> None:
            """Update weather data."""
            if self.weather.set_coordinates():
                await self.async_refresh()

        self._unsub_track_home = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, _async_update_weather_data
        )

    def untrack_home(self) -> None:
        """Stop tracking changes to HA home setting."""
        if self._unsub_track_home:
            self._unsub_track_home()
            self._unsub_track_home = None
