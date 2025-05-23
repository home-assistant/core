"""Data coordinator for the OpenWeatherMap (OWM) service."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from pyopenweathermap import (
    AirPollutionReport,
    CurrentAirPollution,
    CurrentWeather,
    DailyWeatherForecast,
    HourlyWeatherForecast,
    MinutelyWeatherForecast,
    OWMClient,
    RequestError,
    WeatherReport,
)

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_SUNNY,
    Forecast,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import sun
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from . import OpenweathermapConfigEntry

from .const import (
    ATTR_API_AIRPOLLUTION_AQI,
    ATTR_API_AIRPOLLUTION_CO,
    ATTR_API_AIRPOLLUTION_NH3,
    ATTR_API_AIRPOLLUTION_NO,
    ATTR_API_AIRPOLLUTION_NO2,
    ATTR_API_AIRPOLLUTION_O3,
    ATTR_API_AIRPOLLUTION_PM2_5,
    ATTR_API_AIRPOLLUTION_PM10,
    ATTR_API_AIRPOLLUTION_SO2,
    ATTR_API_CLOUDS,
    ATTR_API_CONDITION,
    ATTR_API_CURRENT,
    ATTR_API_DAILY_FORECAST,
    ATTR_API_DATETIME,
    ATTR_API_DEW_POINT,
    ATTR_API_FEELS_LIKE_TEMPERATURE,
    ATTR_API_FORECAST,
    ATTR_API_HOURLY_FORECAST,
    ATTR_API_HUMIDITY,
    ATTR_API_MINUTE_FORECAST,
    ATTR_API_PRECIPITATION,
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
    OWM_MODE_AIRPOLLUTION,
    OWM_MODE_FREE_CURRENT,
    OWM_MODE_FREE_FORECAST,
    OWM_MODE_V30,
    WEATHER_CODE_SUNNY_OR_CLEAR_NIGHT,
)

_LOGGER = logging.getLogger(__name__)

OWM_UPDATE_INTERVAL = timedelta(minutes=10)


class OWMUpdateCoordinator(DataUpdateCoordinator):
    """OWM data update coordinator."""

    config_entry: OpenweathermapConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OpenweathermapConfigEntry,
        owm_client: OWMClient,
    ) -> None:
        """Initialize coordinator."""
        self._owm_client = owm_client
        self._latitude = config_entry.data.get(CONF_LATITUDE, hass.config.latitude)
        self._longitude = config_entry.data.get(CONF_LONGITUDE, hass.config.longitude)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=OWM_UPDATE_INTERVAL,
        )


class WeatherUpdateCoordinator(OWMUpdateCoordinator):
    """Weather data update coordinator."""

    async def _async_update_data(self):
        """Update the data."""
        try:
            weather_report = await self._owm_client.get_weather(
                self._latitude, self._longitude
            )
        except RequestError as error:
            raise UpdateFailed(error) from error
        return self._convert_weather_response(weather_report)

    def _convert_weather_response(self, weather_report: WeatherReport):
        """Format the weather response correctly."""
        _LOGGER.debug("OWM weather response: %s", weather_report)

        current_weather = (
            self._get_current_weather_data(weather_report.current)
            if weather_report.current is not None
            else {}
        )

        return {
            ATTR_API_CURRENT: current_weather,
            ATTR_API_MINUTE_FORECAST: (
                self._get_minute_weather_data(weather_report.minutely_forecast)
                if weather_report.minutely_forecast is not None
                else {}
            ),
            ATTR_API_HOURLY_FORECAST: [
                self._get_hourly_forecast_weather_data(item)
                for item in weather_report.hourly_forecast
            ],
            ATTR_API_DAILY_FORECAST: [
                self._get_daily_forecast_weather_data(item)
                for item in weather_report.daily_forecast
            ],
        }

    def _get_minute_weather_data(
        self, minute_forecast: list[MinutelyWeatherForecast]
    ) -> dict:
        """Get minute weather data from the forecast."""
        return {
            ATTR_API_FORECAST: [
                {
                    ATTR_API_DATETIME: item.date_time,
                    ATTR_API_PRECIPITATION: round(item.precipitation, 2),
                }
                for item in minute_forecast
            ]
        }

    def _get_current_weather_data(self, current_weather: CurrentWeather):
        return {
            ATTR_API_CONDITION: self._get_condition(current_weather.condition.id),
            ATTR_API_TEMPERATURE: current_weather.temperature,
            ATTR_API_FEELS_LIKE_TEMPERATURE: current_weather.feels_like,
            ATTR_API_PRESSURE: current_weather.pressure,
            ATTR_API_HUMIDITY: current_weather.humidity,
            ATTR_API_DEW_POINT: current_weather.dew_point,
            ATTR_API_CLOUDS: current_weather.cloud_coverage,
            ATTR_API_WIND_SPEED: current_weather.wind_speed,
            ATTR_API_WIND_GUST: current_weather.wind_gust,
            ATTR_API_WIND_BEARING: current_weather.wind_bearing,
            ATTR_API_WEATHER: current_weather.condition.description,
            ATTR_API_WEATHER_CODE: current_weather.condition.id,
            ATTR_API_UV_INDEX: current_weather.uv_index,
            ATTR_API_VISIBILITY_DISTANCE: current_weather.visibility,
            ATTR_API_RAIN: self._get_precipitation_value(current_weather.rain),
            ATTR_API_SNOW: self._get_precipitation_value(current_weather.snow),
            ATTR_API_PRECIPITATION_KIND: self._calc_precipitation_kind(
                current_weather.rain, current_weather.snow
            ),
        }

    def _get_hourly_forecast_weather_data(self, forecast: HourlyWeatherForecast):
        uv_index = float(forecast.uv_index) if forecast.uv_index is not None else None

        return Forecast(
            datetime=forecast.date_time.isoformat(),
            condition=self._get_condition(forecast.condition.id),
            temperature=forecast.temperature,
            native_apparent_temperature=forecast.feels_like,
            pressure=forecast.pressure,
            humidity=forecast.humidity,
            native_dew_point=forecast.dew_point,
            cloud_coverage=forecast.cloud_coverage,
            wind_speed=forecast.wind_speed,
            native_wind_gust_speed=forecast.wind_gust,
            wind_bearing=forecast.wind_bearing,
            uv_index=uv_index,
            precipitation_probability=round(forecast.precipitation_probability * 100),
            precipitation=self._calc_precipitation(forecast.rain, forecast.snow),
        )

    def _get_daily_forecast_weather_data(self, forecast: DailyWeatherForecast):
        uv_index = float(forecast.uv_index) if forecast.uv_index is not None else None

        return Forecast(
            datetime=forecast.date_time.isoformat(),
            condition=self._get_condition(forecast.condition.id),
            temperature=forecast.temperature.max,
            templow=forecast.temperature.min,
            native_apparent_temperature=forecast.feels_like,
            pressure=forecast.pressure,
            humidity=forecast.humidity,
            native_dew_point=forecast.dew_point,
            cloud_coverage=forecast.cloud_coverage,
            wind_speed=forecast.wind_speed,
            native_wind_gust_speed=forecast.wind_gust,
            wind_bearing=forecast.wind_bearing,
            uv_index=uv_index,
            precipitation_probability=round(forecast.precipitation_probability * 100),
            precipitation=round(forecast.rain + forecast.snow, 2),
        )

    @staticmethod
    def _calc_precipitation(rain, snow):
        """Calculate the precipitation."""
        rain_value = WeatherUpdateCoordinator._get_precipitation_value(rain)
        snow_value = WeatherUpdateCoordinator._get_precipitation_value(snow)
        return round(rain_value + snow_value, 2)

    @staticmethod
    def _calc_precipitation_kind(rain, snow):
        """Determine the precipitation kind."""
        rain_value = WeatherUpdateCoordinator._get_precipitation_value(rain)
        snow_value = WeatherUpdateCoordinator._get_precipitation_value(snow)
        if rain_value != 0:
            if snow_value != 0:
                return "Snow and Rain"
            return "Rain"

        if snow_value != 0:
            return "Snow"
        return "None"

    @staticmethod
    def _get_precipitation_value(precipitation):
        """Get precipitation value from weather data."""
        if precipitation is not None:
            if "all" in precipitation:
                return round(precipitation["all"], 2)
            if "3h" in precipitation:
                return round(precipitation["3h"], 2)
            if "1h" in precipitation:
                return round(precipitation["1h"], 2)
        return 0

    def _get_condition(self, weather_code, timestamp=None):
        """Get weather condition from weather data."""
        if weather_code == WEATHER_CODE_SUNNY_OR_CLEAR_NIGHT:
            if timestamp:
                timestamp = dt_util.utc_from_timestamp(timestamp)

            if sun.is_up(self.hass, timestamp):
                return ATTR_CONDITION_SUNNY
            return ATTR_CONDITION_CLEAR_NIGHT

        return CONDITION_MAP.get(weather_code)


class AirPollutionUpdateCoordinator(OWMUpdateCoordinator):
    """Air Pollution data update coordinator."""

    async def _async_update_data(self):
        """Update the data."""
        try:
            air_pollution_report = await self._owm_client.get_air_pollution(
                self._latitude, self._longitude
            )
        except RequestError as error:
            raise UpdateFailed(error) from error
        return self._convert_air_pollution_response(air_pollution_report)

    def _convert_air_pollution_response(self, air_pollution_report: AirPollutionReport):
        """Format the air pollution response correctly."""
        _LOGGER.debug("OWM air pollution response: %s", air_pollution_report)

        current_air_pollution = (
            self._get_current_air_pollution_data(air_pollution_report.current)
            if air_pollution_report.current is not None
            else {}
        )

        return {
            ATTR_API_CURRENT: current_air_pollution,
        }

    def _get_current_air_pollution_data(
        self, current_air_pollution: CurrentAirPollution
    ):
        return {
            ATTR_API_AIRPOLLUTION_AQI: current_air_pollution.aqi,
            ATTR_API_AIRPOLLUTION_CO: current_air_pollution.co,
            ATTR_API_AIRPOLLUTION_NO: current_air_pollution.no,
            ATTR_API_AIRPOLLUTION_NO2: current_air_pollution.no2,
            ATTR_API_AIRPOLLUTION_O3: current_air_pollution.o3,
            ATTR_API_AIRPOLLUTION_SO2: current_air_pollution.so2,
            ATTR_API_AIRPOLLUTION_PM2_5: current_air_pollution.pm2_5,
            ATTR_API_AIRPOLLUTION_PM10: current_air_pollution.pm10,
            ATTR_API_AIRPOLLUTION_NH3: current_air_pollution.nh3,
        }


def get_owm_update_coordinator(mode: str) -> type[OWMUpdateCoordinator]:
    """Create coordinator with a factory."""
    coordinators = {
        OWM_MODE_V30: WeatherUpdateCoordinator,
        OWM_MODE_FREE_CURRENT: WeatherUpdateCoordinator,
        OWM_MODE_FREE_FORECAST: WeatherUpdateCoordinator,
        OWM_MODE_AIRPOLLUTION: AirPollutionUpdateCoordinator,
    }

    return coordinators[mode]
