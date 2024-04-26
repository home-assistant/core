"""Weather data coordinator for the OpenWeatherMap (OWM) service."""

import asyncio
from datetime import timedelta
import logging

from pyopenweathermap import (
    CurrentWeather,
    DailyWeatherForecast,
    HourlyWeatherForecast,
    OWMClient,
    WeatherReport,
)
from pyowm.commons.exceptions import APIRequestError, UnauthorizedError

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_SUNNY,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import sun
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_API_CLOUDS,
    ATTR_API_CONDITION,
    ATTR_API_CURRENT,
    ATTR_API_DAILY_FORECAST,
    ATTR_API_DEW_POINT,
    ATTR_API_FEELS_LIKE_TEMPERATURE,
    ATTR_API_FORECAST,
    ATTR_API_FORECAST_CLOUDS,
    ATTR_API_FORECAST_CONDITION,
    ATTR_API_FORECAST_FEELS_LIKE_TEMPERATURE,
    ATTR_API_FORECAST_HUMIDITY,
    ATTR_API_FORECAST_PRECIPITATION,
    ATTR_API_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_API_FORECAST_PRESSURE,
    ATTR_API_FORECAST_TEMP,
    ATTR_API_FORECAST_TEMP_LOW,
    ATTR_API_FORECAST_TIME,
    ATTR_API_FORECAST_WIND_BEARING,
    ATTR_API_FORECAST_WIND_SPEED,
    ATTR_API_HOURLY_FORECAST,
    ATTR_API_HUMIDITY,
    ATTR_API_PRECIPITATION_KIND,
    ATTR_API_PRESSURE,
    ATTR_API_RAIN,
    ATTR_API_SNOW,
    ATTR_API_TEMPERATURE,
    ATTR_API_UV_INDEX,
    ATTR_API_VISIBILITY_DISTANCE,
    ATTR_API_WEATHER,
    ATTR_API_WEATHER_CODE,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_GUST,
    ATTR_API_WIND_SPEED,
    CONDITION_MAP,
    DOMAIN,
    FORECAST_MODE_DAILY,
    FORECAST_MODE_HOURLY,
    FORECAST_MODE_ONECALL_DAILY,
    FORECAST_MODE_ONECALL_HOURLY,
    WEATHER_CODE_SUNNY_OR_CLEAR_NIGHT,
)

_LOGGER = logging.getLogger(__name__)

WEATHER_UPDATE_INTERVAL = timedelta(minutes=10)


class WeatherUpdateCoordinator(DataUpdateCoordinator):  # pylint: disable=hass-enforce-coordinator-module
    """Weather data update coordinator."""

    def __init__(
        self,
        owm_client: OWMClient,
        owm,
        latitude,
        longitude,
        forecast_mode,
        hass: HomeAssistant,
    ) -> None:
        """Initialize coordinator."""
        self._owm_client = owm_client
        self._owm_client_old = owm
        self._latitude = latitude
        self._longitude = longitude
        self.forecast_mode = forecast_mode
        self._forecast_limit = None
        if forecast_mode == FORECAST_MODE_DAILY:
            self._forecast_limit = 15

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=WEATHER_UPDATE_INTERVAL
        )

    async def _async_update_data(self):
        """Update the data."""
        data = {}
        async with asyncio.timeout(20):
            try:
                weather_report = await self._owm_client.get_weather(
                    self._latitude, self._longitude
                )
                weather_response_old = await self._get_owm_weather()
                data = self._convert_weather_response(
                    weather_report, weather_response_old
                )
            except (APIRequestError, UnauthorizedError) as error:
                raise UpdateFailed(error) from error
        return data

    async def _get_owm_weather(self):
        """Poll weather data from OWM."""
        if self.forecast_mode in (
            FORECAST_MODE_ONECALL_HOURLY,
            FORECAST_MODE_ONECALL_DAILY,
        ):
            weather = await self.hass.async_add_executor_job(
                self._owm_client_old.one_call, self._latitude, self._longitude
            )
        else:
            weather = await self.hass.async_add_executor_job(
                self._get_legacy_weather_and_forecast
            )

        return weather

    def _get_legacy_weather_and_forecast(self):
        """Get weather and forecast data from OWM."""
        interval = self._get_legacy_forecast_interval()
        weather = self._owm_client_old.weather_at_coords(
            self._latitude, self._longitude
        )
        forecast = self._owm_client_old.forecast_at_coords(
            self._latitude, self._longitude, interval, self._forecast_limit
        )
        return LegacyWeather(weather.weather, forecast.forecast.weathers)

    def _get_legacy_forecast_interval(self):
        """Get the correct forecast interval depending on the forecast mode."""
        interval = "daily"
        if self.forecast_mode == FORECAST_MODE_HOURLY:
            interval = "3h"
        return interval

    def _convert_weather_response(
        self, weather_report: WeatherReport, weather_response_old
    ):
        """Format the weather response correctly."""
        current_weather_old = weather_response_old.current
        forecast_weather_old = self._get_forecast_from_weather_response(
            weather_response_old
        )

        return {
            ATTR_API_CURRENT: self._get_current_weather_data(weather_report.current),
            ATTR_API_HOURLY_FORECAST: [
                self._get_hourly_forecast_weather_data(item)
                for item in weather_report.hourly_forecast
            ],
            ATTR_API_DAILY_FORECAST: [
                self._get_daily_forecast_weather_data(item)
                for item in weather_report.daily_forecast
            ],
            ATTR_API_RAIN: self._get_rain(current_weather_old.rain),
            ATTR_API_SNOW: self._get_snow(current_weather_old.snow),
            ATTR_API_PRECIPITATION_KIND: self._calc_precipitation_kind(
                current_weather_old.rain, current_weather_old.snow
            ),
            ATTR_API_FORECAST: forecast_weather_old,
        }

    def _get_current_weather_data(self, current_weather: CurrentWeather):
        return {
            ATTR_API_CONDITION: self._get_condition(current_weather.get_weather().id),
            ATTR_API_TEMPERATURE: current_weather.temperature,
            ATTR_API_FEELS_LIKE_TEMPERATURE: current_weather.feels_like,
            ATTR_API_PRESSURE: current_weather.pressure,
            ATTR_API_HUMIDITY: current_weather.humidity,
            ATTR_API_DEW_POINT: current_weather.dew_point,
            ATTR_API_CLOUDS: current_weather.clouds,
            ATTR_API_WIND_SPEED: current_weather.wind_speed,
            ATTR_API_WIND_GUST: current_weather.wind_gust,
            ATTR_API_WIND_BEARING: str(current_weather.wind_deg),
            ATTR_API_WEATHER: current_weather.get_weather().description,
            ATTR_API_WEATHER_CODE: current_weather.get_weather().id,
            ATTR_API_UV_INDEX: current_weather.uv_index,
            ATTR_API_VISIBILITY_DISTANCE: current_weather.visibility,
        }

    def _get_hourly_forecast_weather_data(self, forecast: HourlyWeatherForecast):
        return {
            ATTR_API_FORECAST_TIME: {},
            ATTR_API_CONDITION: self._get_condition(forecast.get_weather().id),
            ATTR_API_TEMPERATURE: forecast.temperature,
            ATTR_API_FEELS_LIKE_TEMPERATURE: forecast.feels_like,
            ATTR_API_PRESSURE: forecast.pressure,
            ATTR_API_HUMIDITY: forecast.humidity,
            ATTR_API_DEW_POINT: forecast.dew_point,
            ATTR_API_CLOUDS: forecast.clouds,
            ATTR_API_WIND_SPEED: forecast.wind_speed,
            ATTR_API_WIND_GUST: forecast.wind_gust,
            ATTR_API_WIND_BEARING: str(forecast.wind_deg),
            ATTR_API_WEATHER: forecast.get_weather().description,
            ATTR_API_WEATHER_CODE: forecast.get_weather().id,
            ATTR_API_UV_INDEX: forecast.uv_index,
            ATTR_API_VISIBILITY_DISTANCE: forecast.visibility,
            ATTR_API_FORECAST_PRECIPITATION_PROBABILITY: forecast.precipitation_probability,
            ATTR_API_FORECAST_PRECIPITATION: {},
        }

    def _get_daily_forecast_weather_data(self, forecast: DailyWeatherForecast):
        return {
            ATTR_API_FORECAST_TIME: {},
            ATTR_API_CONDITION: self._get_condition(forecast.get_weather().id),
            ATTR_API_TEMPERATURE: forecast.temperature.max,
            ATTR_API_FORECAST_TEMP_LOW: forecast.temperature.min,
            ATTR_API_FEELS_LIKE_TEMPERATURE: forecast.feels_like.day,
            ATTR_API_PRESSURE: forecast.pressure,
            ATTR_API_HUMIDITY: forecast.humidity,
            ATTR_API_DEW_POINT: forecast.dew_point,
            ATTR_API_CLOUDS: forecast.clouds,
            ATTR_API_WIND_SPEED: forecast.wind_speed,
            ATTR_API_WIND_GUST: forecast.wind_gust,
            ATTR_API_WIND_BEARING: str(forecast.wind_deg),
            ATTR_API_WEATHER: forecast.get_weather().description,
            ATTR_API_WEATHER_CODE: forecast.get_weather().id,
            ATTR_API_UV_INDEX: forecast.uv_index,
            ATTR_API_VISIBILITY_DISTANCE: forecast.visibility,
            ATTR_API_FORECAST_PRECIPITATION_PROBABILITY: forecast.precipitation_probability,
            ATTR_API_FORECAST_PRECIPITATION: {},
        }

    def _get_forecast_from_weather_response(self, weather_response):
        """Extract the forecast data from the weather response."""
        forecast_arg = "forecast"
        if self.forecast_mode == FORECAST_MODE_ONECALL_HOURLY:
            forecast_arg = "forecast_hourly"
        elif self.forecast_mode == FORECAST_MODE_ONECALL_DAILY:
            forecast_arg = "forecast_daily"
        return [
            self._convert_forecast(x) for x in getattr(weather_response, forecast_arg)
        ]

    def _convert_forecast(self, entry):
        """Convert the forecast data."""
        forecast = {
            ATTR_API_FORECAST_TIME: dt_util.utc_from_timestamp(
                entry.reference_time("unix")
            ).isoformat(),
            ATTR_API_FORECAST_PRECIPITATION: self._calc_precipitation(
                entry.rain, entry.snow
            ),
            ATTR_API_FORECAST_PRECIPITATION_PROBABILITY: (
                round(entry.precipitation_probability * 100)
            ),
            ATTR_API_FORECAST_PRESSURE: entry.pressure.get("press"),
            ATTR_API_FORECAST_WIND_SPEED: entry.wind().get("speed"),
            ATTR_API_FORECAST_WIND_BEARING: entry.wind().get("deg"),
            ATTR_API_FORECAST_CONDITION: self._get_condition(
                entry.weather_code, entry.reference_time("unix")
            ),
            ATTR_API_FORECAST_CLOUDS: entry.clouds,
            ATTR_API_FORECAST_FEELS_LIKE_TEMPERATURE: entry.temperature("celsius").get(
                "feels_like_day"
            ),
            ATTR_API_FORECAST_HUMIDITY: entry.humidity,
        }

        temperature_dict = entry.temperature("celsius")
        if "max" in temperature_dict and "min" in temperature_dict:
            forecast[ATTR_API_FORECAST_TEMP] = entry.temperature("celsius").get("max")
            forecast[ATTR_API_FORECAST_TEMP_LOW] = entry.temperature("celsius").get(
                "min"
            )
        else:
            forecast[ATTR_API_FORECAST_TEMP] = entry.temperature("celsius").get("temp")

        return forecast

    @staticmethod
    def _get_rain(rain):
        """Get rain data from weather data."""
        if "all" in rain:
            return round(rain["all"], 2)
        if "3h" in rain:
            return round(rain["3h"], 2)
        if "1h" in rain:
            return round(rain["1h"], 2)
        return 0

    @staticmethod
    def _get_snow(snow):
        """Get snow data from weather data."""
        if snow:
            if "all" in snow:
                return round(snow["all"], 2)
            if "3h" in snow:
                return round(snow["3h"], 2)
            if "1h" in snow:
                return round(snow["1h"], 2)
        return 0

    @staticmethod
    def _calc_precipitation(rain, snow):
        """Calculate the precipitation."""
        rain_value = 0
        if WeatherUpdateCoordinator._get_rain(rain) != 0:
            rain_value = WeatherUpdateCoordinator._get_rain(rain)

        snow_value = 0
        if WeatherUpdateCoordinator._get_snow(snow) != 0:
            snow_value = WeatherUpdateCoordinator._get_snow(snow)

        return round(rain_value + snow_value, 2)

    @staticmethod
    def _calc_precipitation_kind(rain, snow):
        """Determine the precipitation kind."""
        if WeatherUpdateCoordinator._get_rain(rain) != 0:
            if WeatherUpdateCoordinator._get_snow(snow) != 0:
                return "Snow and Rain"
            return "Rain"

        if WeatherUpdateCoordinator._get_snow(snow) != 0:
            return "Snow"
        return "None"

    def _get_condition(self, weather_code, timestamp=None):
        """Get weather condition from weather data."""
        if weather_code == WEATHER_CODE_SUNNY_OR_CLEAR_NIGHT:
            if timestamp:
                timestamp = dt_util.utc_from_timestamp(timestamp)

            if sun.is_up(self.hass, timestamp):
                return ATTR_CONDITION_SUNNY
            return ATTR_CONDITION_CLEAR_NIGHT

        return CONDITION_MAP.get(weather_code)


class LegacyWeather:
    """Class to harmonize weather data model for hourly, daily and One Call APIs."""

    def __init__(self, current_weather, forecast):
        """Initialize weather object."""
        self.current = current_weather
        self.forecast = forecast
