"""Weather data coordinator for the OpenWeatherMap (OWM) service."""
from datetime import timedelta
import logging

import async_timeout
from pyowm.exceptions.api_call_error import APICallError
from pyowm.exceptions.api_response_error import UnauthorizedError

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
                weather_response = await self._get_owm_weather()
                data = self._convert_weather_response(weather_response)
            except (APICallError, UnauthorizedError) as error:
                raise UpdateFailed(error) from error
        return data

    async def _get_owm_weather(self):
        weather = await self.hass.async_add_executor_job(
            self._owm_client.weather_at_coords, self._latitude, self._longitude
        )
        return weather.get_weather()

    def _convert_weather_response(self, weather_response):
        return {
            ATTR_API_TEMPERATURE: weather_response.get_temperature("celsius").get(
                "temp"
            ),
            ATTR_API_PRESSURE: weather_response.get_pressure().get("press"),
            ATTR_API_HUMIDITY: weather_response.get_humidity(),
            ATTR_API_WIND_BEARING: weather_response.get_wind().get("deg"),
            ATTR_API_WIND_SPEED: weather_response.get_wind().get("speed"),
            ATTR_API_CLOUDS: weather_response.get_clouds(),
            ATTR_API_RAIN: self._get_rain(weather_response.get_rain()),
            ATTR_API_SNOW: self._get_snow(weather_response.get_snow()),
            ATTR_API_WEATHER: weather_response.get_detailed_status(),
            ATTR_API_CONDITION: self._get_condition(
                weather_response.get_weather_code()
            ),
            ATTR_API_WEATHER_CODE: weather_response.get_weather_code(),
        }

    @staticmethod
    def _get_rain(rain):
        if "1h" in rain:
            return round(rain["1h"], 0)
        return "not raining"

    @staticmethod
    def _get_snow(snow):
        if snow:
            return round(snow, 0)
        return "not snowing"

    @staticmethod
    def _get_condition(weather_code):
        return [k for k, v in CONDITION_CLASSES.items() if weather_code in v][0]
