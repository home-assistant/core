"""Weather data coordinator for the OpenWeatherMap (OWM) service."""
from datetime import timedelta
import logging

import async_timeout
from pyowm.exceptions.api_call_error import APICallError

from homeassistant.const import PRESSURE_PA, TEMP_CELSIUS
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_API_CLOUDS,
    ATTR_API_CONDITION,
    ATTR_API_HUMIDITY,
    ATTR_API_PRESSURE,
    ATTR_API_TEMP,
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
        self._units = hass.config.units

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=WEATHER_UPDATE_INTERVAL
        )

    async def _async_update_data(self):
        data = {}
        with async_timeout.timeout(20):
            try:
                weather_response = await self._update_weather()
            except APICallError as error:
                raise UpdateFailed(error)

        data[ATTR_API_WEATHER] = weather_response.get_detailed_status()
        data[ATTR_API_TEMP] = self._units.temperature(
            float(weather_response.get_temperature("celsius").get("temp")), TEMP_CELSIUS
        )
        data[ATTR_API_PRESSURE] = self._units.pressure(
            weather_response.get_pressure().get("press"), PRESSURE_PA
        )
        data[ATTR_API_HUMIDITY] = weather_response.get_humidity()
        data[ATTR_API_CONDITION] = _get_weather_condition(weather_response)
        data[ATTR_API_WIND_BEARING] = weather_response.get_wind().get("deg")
        data[ATTR_API_WIND_SPEED] = weather_response.get_wind().get("speed")
        data[ATTR_API_CLOUDS] = weather_response.get_clouds()
        data[ATTR_API_WEATHER_CODE] = weather_response.get_weather_code()

        return data

    async def _update_weather(self):
        weather = self._owm_client.weather_at_coords(self._latitude, self._longitude)
        return weather.get_weather()


def _get_weather_condition(weather_response):
    return [
        key
        for key, value in CONDITION_CLASSES.items()
        if weather_response.get_weather_code() in value
    ][0]
