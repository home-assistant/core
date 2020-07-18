"""Weather data coordinator for the OpenWeatherMap (OWM) service."""
from datetime import timedelta
import logging

import async_timeout
from pyowm.exceptions.api_call_error import APICallError
from pyowm.exceptions.api_response_error import UnauthorizedError

from homeassistant.const import PRESSURE_PA, TEMP_CELSIUS
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_API_CLOUDS,
    ATTR_API_CONDITION,
    ATTR_API_HUMIDITY,
    ATTR_API_PRESSURE,
    ATTR_API_RAIN,
    ATTR_API_SNOW,
    ATTR_API_TEMPERATURE,
    ATTR_API_WEATHER,
    ATTR_API_WEATHER_CODE,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_SPEED,
    CONDITION_CLASSES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

WEATHER_UPDATE_INTERVAL = timedelta(minutes=10)


class WeatherUpdateCoordinator(DataUpdateCoordinator):
    """Weather data update coordinator."""

    def __init__(self, owm, latitude, longitude, hass):
        """Initialize coordinator."""
        self._owm_client = owm
        self._latitude = latitude
        self._longitude = longitude

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=WEATHER_UPDATE_INTERVAL
        )

    async def _async_update_data(self):
        data = {}
        with async_timeout.timeout(20):
            try:
                weather_response = await self._update_weather()
                data = self._convert_weather_response(weather_response)
            except (APICallError, UnauthorizedError) as error:
                raise UpdateFailed(error)
        return data

    async def _update_weather(self):
        weather = await self.hass.async_add_executor_job(
            self._owm_client.weather_at_coords, self._latitude, self._longitude
        )
        return weather.get_weather()

    def _convert_weather_response(self, weather_response):
        return {
            ATTR_API_TEMPERATURE: _get_temperature_in_current_unit(
                self.hass, weather_response.get_temperature("celsius").get("temp")
            ),
            ATTR_API_PRESSURE: _get_pressure_in_current_unit(
                self.hass, weather_response.get_pressure().get("press")
            ),
            ATTR_API_HUMIDITY: weather_response.get_humidity(),
            ATTR_API_WIND_BEARING: weather_response.get_wind().get("deg"),
            ATTR_API_WIND_SPEED: weather_response.get_wind().get("speed"),
            ATTR_API_CLOUDS: weather_response.get_clouds(),
            ATTR_API_RAIN: _get_rain(weather_response.get_rain()),
            ATTR_API_SNOW: _get_snow(weather_response.get_snow()),
            ATTR_API_WEATHER: weather_response.get_detailed_status(),
            ATTR_API_CONDITION: _get_condition(weather_response.get_weather_code()),
            ATTR_API_WEATHER_CODE: weather_response.get_weather_code(),
        }


def _get_temperature_in_current_unit(hass, value):
    return hass.config.units.temperature(float(value), TEMP_CELSIUS)


def _get_pressure_in_current_unit(hass, value):
    return hass.config.units.pressure(value, PRESSURE_PA)


def _get_rain(rain):
    if "3h" in rain:
        return round(rain["3h"], 0)
    return "not raining"


def _get_snow(snow):
    if snow:
        return round(snow, 0)
    return "not snowing"


def _get_condition(weather_code):
    return [k for k, v in CONDITION_CLASSES.items() if weather_code in v][0]
