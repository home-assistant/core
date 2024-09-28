"""Constants for weather."""

from __future__ import annotations

from collections.abc import Callable
from enum import IntFlag
from typing import TYPE_CHECKING, Final

from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
)

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import WeatherEntity


class WeatherEntityFeature(IntFlag):
    """Supported features of the update entity."""

    FORECAST_DAILY = 1
    FORECAST_HOURLY = 2
    FORECAST_TWICE_DAILY = 4


ATTR_WEATHER_HUMIDITY = "humidity"
ATTR_WEATHER_OZONE = "ozone"
ATTR_WEATHER_DEW_POINT = "dew_point"
ATTR_WEATHER_PRESSURE = "pressure"
ATTR_WEATHER_PRESSURE_UNIT = "pressure_unit"
ATTR_WEATHER_APPARENT_TEMPERATURE = "apparent_temperature"
ATTR_WEATHER_TEMPERATURE = "temperature"
ATTR_WEATHER_TEMPERATURE_UNIT = "temperature_unit"
ATTR_WEATHER_VISIBILITY = "visibility"
ATTR_WEATHER_VISIBILITY_UNIT = "visibility_unit"
ATTR_WEATHER_WIND_BEARING = "wind_bearing"
ATTR_WEATHER_WIND_GUST_SPEED = "wind_gust_speed"
ATTR_WEATHER_WIND_SPEED = "wind_speed"
ATTR_WEATHER_WIND_SPEED_UNIT = "wind_speed_unit"
ATTR_WEATHER_PRECIPITATION_UNIT = "precipitation_unit"
ATTR_WEATHER_CLOUD_COVERAGE = "cloud_coverage"
ATTR_WEATHER_UV_INDEX = "uv_index"

DOMAIN: Final = "weather"
DATA_COMPONENT: HassKey[EntityComponent[WeatherEntity]] = HassKey(DOMAIN)

INTENT_GET_WEATHER = "HassGetWeather"

VALID_UNITS_PRESSURE: set[str] = {
    UnitOfPressure.HPA,
    UnitOfPressure.MBAR,
    UnitOfPressure.INHG,
    UnitOfPressure.MMHG,
}
VALID_UNITS_TEMPERATURE: set[str] = {
    UnitOfTemperature.CELSIUS,
    UnitOfTemperature.FAHRENHEIT,
}
VALID_UNITS_PRECIPITATION: set[str] = {
    UnitOfPrecipitationDepth.MILLIMETERS,
    UnitOfPrecipitationDepth.INCHES,
}
VALID_UNITS_VISIBILITY: set[str] = {
    UnitOfLength.KILOMETERS,
    UnitOfLength.MILES,
}
VALID_UNITS_WIND_SPEED: set[str] = {
    UnitOfSpeed.FEET_PER_SECOND,
    UnitOfSpeed.KILOMETERS_PER_HOUR,
    UnitOfSpeed.KNOTS,
    UnitOfSpeed.METERS_PER_SECOND,
    UnitOfSpeed.MILES_PER_HOUR,
}

UNIT_CONVERSIONS: dict[str, Callable[[float, str, str], float]] = {
    ATTR_WEATHER_PRESSURE_UNIT: PressureConverter.convert,
    ATTR_WEATHER_TEMPERATURE_UNIT: TemperatureConverter.convert,
    ATTR_WEATHER_VISIBILITY_UNIT: DistanceConverter.convert,
    ATTR_WEATHER_PRECIPITATION_UNIT: DistanceConverter.convert,
    ATTR_WEATHER_WIND_SPEED_UNIT: SpeedConverter.convert,
}

VALID_UNITS: dict[str, set[str]] = {
    ATTR_WEATHER_PRESSURE_UNIT: VALID_UNITS_PRESSURE,
    ATTR_WEATHER_TEMPERATURE_UNIT: VALID_UNITS_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY_UNIT: VALID_UNITS_VISIBILITY,
    ATTR_WEATHER_PRECIPITATION_UNIT: VALID_UNITS_PRECIPITATION,
    ATTR_WEATHER_WIND_SPEED_UNIT: VALID_UNITS_WIND_SPEED,
}
