"""Provide a mock weather platform.

Call init before using it in your tests to ensure clean test data.
"""
from __future__ import annotations

from homeassistant.components.weather import (
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRESSURE,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    Forecast,
    WeatherEntity,
)

from tests.common import MockEntity

ENTITIES = []


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES
    ENTITIES = [] if empty else [MockWeather()]


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
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
    def native_visibility(self) -> float | None:
        """Return the visibility."""
        return self._handle("native_visibility")

    @property
    def native_visibility_unit(self) -> str | None:
        """Return the unit of measurement for visibility."""
        return self._handle("native_visibility_unit")

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast."""
        return self._handle("forecast")

    @property
    def native_precipitation_unit(self) -> str | None:
        """Return the native unit of measurement for accumulated precipitation."""
        return self._handle("native_precipitation_unit")

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return self._handle("condition")


class MockWeatherCompat(MockEntity, WeatherEntity):
    """Mock weather class for backwards compatibility check."""

    @property
    def temperature(self) -> float | None:
        """Return the platform temperature."""
        return self._handle("temperature")

    @property
    def temperature_unit(self) -> str | None:
        """Return the unit of measurement for temperature."""
        return self._handle("temperature_unit")

    @property
    def pressure(self) -> float | None:
        """Return the pressure."""
        return self._handle("pressure")

    @property
    def pressure_unit(self) -> str | None:
        """Return the unit of measurement for pressure."""
        return self._handle("pressure_unit")

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self._handle("humidity")

    @property
    def wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self._handle("wind_speed")

    @property
    def wind_speed_unit(self) -> str | None:
        """Return the unit of measurement for wind speed."""
        return self._handle("wind_speed_unit")

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self._handle("wind_bearing")

    @property
    def ozone(self) -> float | None:
        """Return the ozone level."""
        return self._handle("ozone")

    @property
    def visibility(self) -> float | None:
        """Return the visibility."""
        return self._handle("visibility")

    @property
    def visibility_unit(self) -> str | None:
        """Return the unit of measurement for visibility."""
        return self._handle("visibility_unit")

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast."""
        return self._handle("forecast")

    @property
    def precipitation_unit(self) -> str | None:
        """Return the unit of measurement for accumulated precipitation."""
        return self._handle("precipitation_unit")

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return self._handle("condition")


class MockWeatherMockForecast(MockWeather):
    """Mock weather class with mocked forecast."""

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast."""
        return [
            {
                ATTR_FORECAST_NATIVE_TEMP: self.native_temperature,
                ATTR_FORECAST_NATIVE_TEMP_LOW: self.native_temperature,
                ATTR_FORECAST_NATIVE_PRESSURE: self.native_pressure,
                ATTR_FORECAST_NATIVE_WIND_SPEED: self.native_wind_speed,
                ATTR_FORECAST_WIND_BEARING: self.wind_bearing,
                ATTR_FORECAST_NATIVE_PRECIPITATION: self._values.get(
                    "native_precipitation"
                ),
            }
        ]


class MockWeatherMockForecastCompat(MockWeatherCompat):
    """Mock weather class with mocked forecast for compatibility check."""

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast."""
        return [
            {
                ATTR_FORECAST_TEMP: self.temperature,
                ATTR_FORECAST_TEMP_LOW: self.temperature,
                ATTR_FORECAST_PRESSURE: self.pressure,
                ATTR_FORECAST_WIND_SPEED: self.wind_speed,
                ATTR_FORECAST_WIND_BEARING: self.wind_bearing,
                ATTR_FORECAST_PRECIPITATION: self._values.get("precipitation"),
            }
        ]
