"""Forecast data coordinator for the OpenWeatherMap (OWM) service."""
from datetime import timedelta
import logging

import async_timeout
from pyowm.commons.exceptions import APIRequestError, UnauthorizedError

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
)
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
        self._weather_manager = owm.weather_manager()
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
                forecast_response = await self._get_owm_forecast()
                data = self._convert_forecast_response(forecast_response)
            except (APIRequestError, UnauthorizedError) as error:
                raise UpdateFailed(error) from error

        return data

    async def _get_owm_forecast(self):
        if self._forecast_mode == "daily":
            forecast_response = await self.hass.async_add_executor_job(
                self._weather_manager.forecast_at_coords,
                self._latitude,
                self._longitude,
                "daily",
                self._forecast_limit,
            )
        else:
            # "freedaily" gets data from 3h as well
            forecast_response = await self.hass.async_add_executor_job(
                self._weather_manager.forecast_at_coords,
                self._latitude,
                self._longitude,
                "3h",
            )
        return forecast_response.forecast

    def _convert_forecast_response(self, forecast_response):
        weathers = self._get_weathers(forecast_response)

        forecast_entries = self._convert_forecast_entries(weathers)

        return {
            ATTR_API_FORECAST: forecast_entries,
            ATTR_API_THIS_DAY_FORECAST: forecast_entries[0],
        }

    def _get_weathers(self, forecast_response):
        if self._forecast_mode == "freedaily":
            return forecast_response.weathers[::8]
        return forecast_response.weathers

    def _convert_forecast_entries(self, entries):
        if self._forecast_mode == "daily":
            return list(map(self._convert_daily_forecast, entries))
        return list(map(self._convert_forecast, entries))

    def _convert_daily_forecast(self, entry):
        return {
            ATTR_FORECAST_TIME: entry.reference_time(timeformat="unix") * 1000,
            ATTR_FORECAST_TEMP: entry.temperature(unit="celsius")["day"],
            ATTR_FORECAST_TEMP_LOW: entry.temperature(unit="celsius")["night"],
            ATTR_FORECAST_PRECIPITATION: self._calc_daily_precipitation(
                entry.rain["all"], entry.snow["all"]
            ),
            ATTR_FORECAST_WIND_SPEED: entry.wind()["speed"],
            ATTR_FORECAST_WIND_BEARING: entry.wind()["deg"],
            ATTR_FORECAST_CONDITION: self._get_condition(entry.weather_code),
        }

    def _convert_forecast(self, entry):
        return {
            ATTR_FORECAST_TIME: entry.reference_time(timeformat="unix") * 1000,
            ATTR_FORECAST_TEMP: entry.temperature(unit="celsius")["temp"],
            ATTR_FORECAST_PRECIPITATION: self._calc_precipitation(entry),
            ATTR_FORECAST_WIND_SPEED: entry.wind()["speed"],
            ATTR_FORECAST_WIND_BEARING: entry.wind()["deg"],
            ATTR_FORECAST_CONDITION: self._get_condition(entry.weather_code),
        }

    @staticmethod
    def _calc_daily_precipitation(rain, snow):
        """Calculate the precipitation."""
        rain_value = 0 if rain is None else rain
        snow_value = 0 if snow is None else snow
        if round(rain_value + snow_value, 1) == 0:
            return None
        return round(rain_value + snow_value, 1)

    @staticmethod
    def _calc_precipitation(entry):
        return (
            round(entry.rain["1h"], 1)
            if "1h" in entry.rain
            and entry.rain["1h"] is not None
            and (round(entry.rain["1h"], 1) > 0)
            else None
        )

    @staticmethod
    def _get_condition(weather_code):
        return [k for k, v in CONDITION_CLASSES.items() if weather_code in v][0]
