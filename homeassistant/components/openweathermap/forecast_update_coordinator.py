"""Forecast data coordinator for the OpenWeatherMap (OWM) service."""
from datetime import timedelta
import logging

import async_timeout
from pyowm.exceptions.api_call_error import APICallError
from pyowm.exceptions.api_response_error import UnauthorizedError

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_API_FORECAST,
    ATTR_API_THIS_DAY_FORECAST,
    CONDITION_CLASSES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

FORECAST_UPDATE_INTERVAL = timedelta(minutes=30)


class ForecastUpdateCoordinator(DataUpdateCoordinator):
    """Forecast data update coordinator."""

    def __init__(self, owm, latitude, longitude, forecast_mode, hass):
        """Initialize coordinator."""
        self._owm_client = owm
        self._forecast_mode = forecast_mode
        self._latitude = latitude
        self._longitude = longitude
        self._forecast_limit = 15

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=FORECAST_UPDATE_INTERVAL
        )

    async def _async_update_data(self):
        data = {}
        with async_timeout.timeout(20):
            try:
                forecast_response = await self._update_forecast()
                data = self._convert_forecast_response(forecast_response)
            except (APICallError, UnauthorizedError) as error:
                raise UpdateFailed(error)

        return data

    async def _update_forecast(self):
        if self._forecast_mode == "daily":
            forecast_response = await self.hass.async_add_executor_job(
                self._owm_client.daily_forecast_at_coords,
                self._latitude,
                self._longitude,
                self._forecast_limit,
            )
        else:
            forecast_response = await self.hass.async_add_executor_job(
                self._owm_client.three_hours_forecast_at_coords,
                self._latitude,
                self._longitude,
            )
        return forecast_response.get_forecast()

    def _convert_forecast_response(self, forecast_response):
        values = self._get_weathers(forecast_response)

        forecast_entries = self._convert_forecast_entries(values)

        return {
            ATTR_API_FORECAST: forecast_entries,
            ATTR_API_THIS_DAY_FORECAST: forecast_entries[0],
        }

    def _convert_forecast_entries(self, values):
        if self._forecast_mode == "daily":
            return list(map(self._convert_daily_forecast, values))
        return list(map(self._convert_forecast, values))

    def _get_weathers(self, forecast_response):
        if self._forecast_mode == "freedaily":
            return forecast_response.get_weathers()[::8]
        return forecast_response.get_weathers()

    def _convert_daily_forecast(self, entry):
        return {
            ATTR_FORECAST_TIME: entry.get_reference_time("unix") * 1000,
            ATTR_FORECAST_TEMP: _get_temperature_in_current_unit(
                self.hass, entry.get_temperature("celsius").get("day")
            ),
            ATTR_FORECAST_TEMP_LOW: _get_temperature_in_current_unit(
                self.hass, entry.get_temperature("celsius").get("night")
            ),
            ATTR_FORECAST_PRECIPITATION: _calc_daily_precipitation(
                entry.get_rain().get("all"), entry.get_snow().get("all")
            ),
            ATTR_FORECAST_WIND_SPEED: entry.get_wind().get("speed"),
            ATTR_FORECAST_WIND_BEARING: entry.get_wind().get("deg"),
            ATTR_FORECAST_CONDITION: _get_condition(entry.get_weather_code()),
        }

    def _convert_forecast(self, entry):
        return {
            ATTR_FORECAST_TIME: entry.get_reference_time("unix") * 1000,
            ATTR_FORECAST_TEMP: _get_temperature_in_current_unit(
                self.hass, entry.get_temperature("celsius").get("temp")
            ),
            ATTR_FORECAST_PRECIPITATION: _calc_precipitation(entry),
            ATTR_FORECAST_WIND_SPEED: entry.get_wind().get("speed"),
            ATTR_FORECAST_WIND_BEARING: entry.get_wind().get("deg"),
            ATTR_FORECAST_CONDITION: _get_condition(entry.get_weather_code()),
        }


def _get_temperature_in_current_unit(hass, value):
    return hass.config.units.temperature(float(value), TEMP_CELSIUS)


def _calc_daily_precipitation(rain, snow):
    """Calculate the precipitation."""
    rain_value = 0 if rain is None else rain
    snow_value = 0 if snow is None else snow
    if round(rain_value + snow_value, 1) == 0:
        return None
    return round(rain_value + snow_value, 1)


def _calc_precipitation(entry):
    return (
        round(entry.get_rain().get("3h"), 1)
        if entry.get_rain().get("3h") is not None
        and (round(entry.get_rain().get("3h"), 1) > 0)
        else None
    )


def _get_condition(weather_code):
    return [k for k, v in CONDITION_CLASSES.items() if weather_code in v][0]
