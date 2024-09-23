"""Provide a mock weather platform.

Call init before using it in your tests to ensure clean test data.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.weather import (
    ATTR_FORECAST_CLOUD_COVERAGE,
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_IS_DAYTIME,
    ATTR_FORECAST_NATIVE_APPARENT_TEMP,
    ATTR_FORECAST_NATIVE_DEW_POINT,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_UV_INDEX,
    ATTR_FORECAST_WIND_BEARING,
    Forecast,
    WeatherEntity,
)
from homeassistant.core import HomeAssistant

from tests.common import MockEntity

ENTITIES = []


def init(empty=False):
    """Initialize the platform with entities."""
    # pylint: disable-next=global-statement
    global ENTITIES  # noqa: PLW0603
    ENTITIES = [] if empty else [MockWeather()]


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)


class MockWeather(MockEntity, WeatherEntity):
    """Mock weather class."""

    @property
    def native_temperature(self) -> float | None:
        """Return the platform temperature."""
        return self._handle("native_temperature")

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the platform apparent temperature."""
        return self._handle("native_apparent_temperature")

    @property
    def native_dew_point(self) -> float | None:
        """Return the platform dewpoint temperature."""
        return self._handle("native_dew_point")

    @property
    def native_temperature_unit(self) -> str | None:
        """Return the unit of measurement for temperature."""
        return self._handle("native_temperature_unit")

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return self._handle("native_pressure")

    @property
    def native_pressure_unit(self) -> str | None:
        """Return the unit of measurement for pressure."""
        return self._handle("native_pressure_unit")

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self._handle("humidity")

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind speed."""
        return self._handle("native_wind_gust_speed")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self._handle("native_wind_speed")

    @property
    def native_wind_speed_unit(self) -> str | None:
        """Return the unit of measurement for wind speed."""
        return self._handle("native_wind_speed_unit")

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self._handle("wind_bearing")

    @property
    def ozone(self) -> float | None:
        """Return the ozone level."""
        return self._handle("ozone")

    @property
    def cloud_coverage(self) -> float | None:
        """Return the cloud coverage in %."""
        return self._handle("cloud_coverage")

    @property
    def uv_index(self) -> float | None:
        """Return the UV index."""
        return self._handle("uv_index")

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility."""
        return self._handle("native_visibility")

    @property
    def native_visibility_unit(self) -> str | None:
        """Return the unit of measurement for visibility."""
        return self._handle("native_visibility_unit")

    @property
    def native_precipitation_unit(self) -> str | None:
        """Return the native unit of measurement for accumulated precipitation."""
        return self._handle("native_precipitation_unit")

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return self._handle("condition")

    @property
    def precision(self) -> float:
        """Return the precision of the temperature."""
        return self._handle("precision")


class MockWeatherMockForecast(MockWeather):
    """Mock weather class with mocked forecast."""

    def __init__(self, **values: Any) -> None:
        """Initialize."""
        super().__init__(**values)
        self.forecast_list: list[Forecast] | None = [
            {
                ATTR_FORECAST_NATIVE_TEMP: self.native_temperature,
                ATTR_FORECAST_NATIVE_APPARENT_TEMP: self.native_apparent_temperature,
                ATTR_FORECAST_NATIVE_TEMP_LOW: self.native_temperature,
                ATTR_FORECAST_NATIVE_DEW_POINT: self.native_dew_point,
                ATTR_FORECAST_CLOUD_COVERAGE: self.cloud_coverage,
                ATTR_FORECAST_NATIVE_PRESSURE: self.native_pressure,
                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: self.native_wind_gust_speed,
                ATTR_FORECAST_NATIVE_WIND_SPEED: self.native_wind_speed,
                ATTR_FORECAST_WIND_BEARING: self.wind_bearing,
                ATTR_FORECAST_UV_INDEX: self.uv_index,
                ATTR_FORECAST_NATIVE_PRECIPITATION: self._values.get(
                    "native_precipitation"
                ),
                ATTR_FORECAST_HUMIDITY: self.humidity,
            }
        ]

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the forecast_daily."""
        return self.forecast_list

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the forecast_twice_daily."""
        return [
            {
                ATTR_FORECAST_NATIVE_TEMP: self.native_temperature,
                ATTR_FORECAST_NATIVE_APPARENT_TEMP: self.native_apparent_temperature,
                ATTR_FORECAST_NATIVE_TEMP_LOW: self.native_temperature,
                ATTR_FORECAST_NATIVE_DEW_POINT: self.native_dew_point,
                ATTR_FORECAST_CLOUD_COVERAGE: self.cloud_coverage,
                ATTR_FORECAST_NATIVE_PRESSURE: self.native_pressure,
                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: self.native_wind_gust_speed,
                ATTR_FORECAST_NATIVE_WIND_SPEED: self.native_wind_speed,
                ATTR_FORECAST_WIND_BEARING: self.wind_bearing,
                ATTR_FORECAST_UV_INDEX: self.uv_index,
                ATTR_FORECAST_NATIVE_PRECIPITATION: self._values.get(
                    "native_precipitation"
                ),
                ATTR_FORECAST_HUMIDITY: self.humidity,
                ATTR_FORECAST_IS_DAYTIME: self._values.get("is_daytime"),
            }
        ]

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the forecast_hourly."""
        return [
            {
                ATTR_FORECAST_NATIVE_TEMP: self.native_temperature,
                ATTR_FORECAST_NATIVE_APPARENT_TEMP: self.native_apparent_temperature,
                ATTR_FORECAST_NATIVE_TEMP_LOW: self.native_temperature,
                ATTR_FORECAST_NATIVE_DEW_POINT: self.native_dew_point,
                ATTR_FORECAST_CLOUD_COVERAGE: self.cloud_coverage,
                ATTR_FORECAST_NATIVE_PRESSURE: self.native_pressure,
                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: self.native_wind_gust_speed,
                ATTR_FORECAST_NATIVE_WIND_SPEED: self.native_wind_speed,
                ATTR_FORECAST_WIND_BEARING: self.wind_bearing,
                ATTR_FORECAST_UV_INDEX: self.uv_index,
                ATTR_FORECAST_NATIVE_PRECIPITATION: self._values.get(
                    "native_precipitation"
                ),
                ATTR_FORECAST_HUMIDITY: self.humidity,
            }
        ]
