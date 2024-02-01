"""Weather data coordinator for the OpenWeatherMap (OWM) service."""
import asyncio
from datetime import timedelta
import logging

from pyowm.commons.exceptions import APIRequestError, UnauthorizedError

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_SUNNY,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers import sun
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    ATTR_API_CLOUDS,
    ATTR_API_CONDITION,
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

    def __init__(self, owm, latitude, longitude, forecast_mode, hass):
        """Initialize coordinator."""
        self._owm_client = owm
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
                weather_response = await self._get_owm_weather()
                data = self._convert_weather_response(weather_response)
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
                self._owm_client.one_call, self._latitude, self._longitude
            )
        else:
            weather = await self.hass.async_add_executor_job(
                self._get_legacy_weather_and_forecast
            )

        return weather

    def _get_legacy_weather_and_forecast(self):
        """Get weather and forecast data from OWM."""
        interval = self._get_legacy_forecast_interval()
        weather = self._owm_client.weather_at_coords(self._latitude, self._longitude)
        forecast = self._owm_client.forecast_at_coords(
            self._latitude, self._longitude, interval, self._forecast_limit
        )
        return LegacyWeather(weather.weather, forecast.forecast.weathers)

    def _get_legacy_forecast_interval(self):
        """Get the correct forecast interval depending on the forecast mode."""
        interval = "daily"
        if self.forecast_mode == FORECAST_MODE_HOURLY:
            interval = "3h"
        return interval

    def _convert_weather_response(self, weather_response):
        """Format the weather response correctly."""
        current_weather = weather_response.current
        forecast_weather = self._get_forecast_from_weather_response(weather_response)

        return {
            ATTR_API_TEMPERATURE: current_weather.temperature("celsius").get("temp"),
            ATTR_API_FEELS_LIKE_TEMPERATURE: current_weather.temperature("celsius").get(
                "feels_like"
            ),
            ATTR_API_DEW_POINT: self._fmt_dewpoint(current_weather.dewpoint),
            ATTR_API_PRESSURE: current_weather.pressure.get("press"),
            ATTR_API_HUMIDITY: current_weather.humidity,
            ATTR_API_WIND_BEARING: current_weather.wind().get("deg"),
            ATTR_API_WIND_GUST: current_weather.wind().get("gust"),
            ATTR_API_WIND_SPEED: current_weather.wind().get("speed"),
            ATTR_API_CLOUDS: current_weather.clouds,
            ATTR_API_RAIN: self._get_rain(current_weather.rain),
            ATTR_API_SNOW: self._get_snow(current_weather.snow),
            ATTR_API_PRECIPITATION_KIND: self._calc_precipitation_kind(
                current_weather.rain, current_weather.snow
            ),
            ATTR_API_WEATHER: current_weather.detailed_status,
            ATTR_API_CONDITION: self._get_condition(current_weather.weather_code),
            ATTR_API_UV_INDEX: current_weather.uvi,
            ATTR_API_VISIBILITY_DISTANCE: current_weather.visibility_distance,
            ATTR_API_WEATHER_CODE: current_weather.weather_code,
            ATTR_API_FORECAST: forecast_weather,
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
    def _fmt_dewpoint(dewpoint):
        """Format the dewpoint data."""
        if dewpoint is not None:
            return round(
                TemperatureConverter.convert(
                    dewpoint, UnitOfTemperature.KELVIN, UnitOfTemperature.CELSIUS
                ),
                1,
            )
        return None

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
