"""DataUpdateCoordinator for the Trafikverket Weather integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from pytrafikverket.exceptions import (
    InvalidAuthentication,
    MultipleWeatherStationsFound,
    NoWeatherStationFound,
)
from pytrafikverket.trafikverket_weather import TrafikverketWeather, WeatherStationInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)
TIME_BETWEEN_UPDATES = timedelta(minutes=10)


class TVDataUpdateCoordinator(DataUpdateCoordinator[WeatherStationInfo]):
    """A Sensibo Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Sensibo coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=TIME_BETWEEN_UPDATES,
        )
        self._weather_api = TrafikverketWeather(
            async_get_clientsession(hass), entry.data[CONF_API_KEY]
        )
        self._station = entry.data[CONF_STATION]

    async def _async_update_data(self) -> WeatherStationInfo:
        """Fetch data from Trafikverket."""
        try:
            weatherdata = await self._weather_api.async_get_weather(self._station)
        except InvalidAuthentication as error:
            raise ConfigEntryAuthFailed from error
        except (NoWeatherStationFound, MultipleWeatherStationsFound) as error:
            raise UpdateFailed from error
        return weatherdata
