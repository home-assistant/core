"""DataUpdateCoordinator for the Trafikverket Weather integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from pytrafikverket.exceptions import (
    InvalidAuthentication,
    MultipleWeatherStationsFound,
    NoWeatherStationFound,
)
from pytrafikverket.models import WeatherStationInfoModel
from pytrafikverket.trafikverket_weather import TrafikverketWeather

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_STATION, DOMAIN

if TYPE_CHECKING:
    from . import TVWeatherConfigEntry

_LOGGER = logging.getLogger(__name__)
TIME_BETWEEN_UPDATES = timedelta(minutes=10)


class TVDataUpdateCoordinator(DataUpdateCoordinator[WeatherStationInfoModel]):
    """A Sensibo Data Update Coordinator."""

    config_entry: TVWeatherConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: TVWeatherConfigEntry) -> None:
        """Initialize the Sensibo coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=TIME_BETWEEN_UPDATES,
        )
        self._weather_api = TrafikverketWeather(
            async_get_clientsession(hass), config_entry.data[CONF_API_KEY]
        )
        self._station = config_entry.data[CONF_STATION]

    async def _async_update_data(self) -> WeatherStationInfoModel:
        """Fetch data from Trafikverket."""
        try:
            weatherdata = await self._weather_api.async_get_weather(self._station)
        except InvalidAuthentication as error:
            raise ConfigEntryAuthFailed from error
        except (NoWeatherStationFound, MultipleWeatherStationsFound) as error:
            raise UpdateFailed from error
        return weatherdata
