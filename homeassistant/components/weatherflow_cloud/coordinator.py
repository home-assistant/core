"""Data coordinator for WeatherFlow Cloud Data."""
from datetime import timedelta
from random import randrange
from types import MappingProxyType
from typing import Any

from pyweatherflow_forecast import (
    WeatherFlow,
    WeatherFlowForecastBadRequest,
    WeatherFlowForecastDaily,
    WeatherFlowForecastData,
    WeatherFlowForecastHourly,
    WeatherFlowForecastInternalServerError,
    WeatherFlowForecastUnauthorized,
    WeatherFlowForecastWongStationId,
    WeatherFlowStationData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    Unauthorized,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, CONF_STATION_ID, DOMAIN


class CannotConnect(HomeAssistantError):
    """Unable to connect to the web site."""


class WeatherFLowCloudData:
    """WeatherFlow REST Data entity."""

    def __init__(self, hass: HomeAssistant, config: MappingProxyType[str, Any]) -> None:
        """Initialise the weather entity data."""

        self.hass = hass
        self._config = config

        self._weather_data = WeatherFlow(
            self._config[CONF_STATION_ID],
            self._config[CONF_API_TOKEN],
            elevation=self.hass.config.elevation,
            session=async_get_clientsession(self.hass),
        )

        self.current_weather_data: WeatherFlowForecastData = {}
        self.daily_forecast: WeatherFlowForecastDaily = []
        self.hourly_forecast: WeatherFlowForecastHourly = []
        self.station_data: WeatherFlowStationData = {}

    async def fetch_forecast_data(self) -> None:
        """Fetch data from API - (current weather and forecast)."""

        try:
            resp: WeatherFlowForecastData = (
                await self._weather_data.async_get_forecast()
            )
        except WeatherFlowForecastWongStationId as unauthorized:
            _LOGGER.debug(unauthorized)
            raise Unauthorized from unauthorized
        except WeatherFlowForecastBadRequest as err:
            _LOGGER.debug(err)
            raise CannotConnect from err
        except WeatherFlowForecastUnauthorized as unauthorized:
            _LOGGER.debug(unauthorized)
            raise Unauthorized from unauthorized
        except WeatherFlowForecastInternalServerError as notreadyerror:
            _LOGGER.debug(notreadyerror)
            raise ConfigEntryNotReady from notreadyerror

        if not resp:
            raise CannotConnect()
        self.current_weather_data = resp
        self.daily_forecast = resp.forecast_daily
        self.hourly_forecast = resp.forecast_hourly


class WeatherFlowCloudDataUpdateCoordinator(
    DataUpdateCoordinator["WeatherFLowCloudData"]
):
    """Class to manage fetching REST Based WeatherFlow Forecast data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize global WeatherFlow forecast data updater."""

        # Store local variables
        self.hass = hass
        self.config_entry = config_entry

        self.weather = WeatherFLowCloudData(hass, config_entry.data)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=randrange(25, 35)),
        )

    async def _async_update_data(self) -> WeatherFLowCloudData:
        """Fetch data from WeatherFlow Forecast."""
        try:
            await self.weather.fetch_forecast_data()
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err

        return self.weather
