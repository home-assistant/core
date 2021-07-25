"""Constants for National Weather Service Integration."""
from __future__ import annotations

from datetime import timedelta
from typing import NamedTuple

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
)
from homeassistant.const import (
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_METERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_INHG,
    PRESSURE_PA,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
)

DOMAIN = "nws"

CONF_STATION = "station"

ATTRIBUTION = "Data from National Weather Service/NOAA"

ATTR_FORECAST_DETAILED_DESCRIPTION = "detailed_description"
ATTR_FORECAST_DAYTIME = "daytime"

CONDITION_CLASSES = {
    ATTR_CONDITION_EXCEPTIONAL: [
        "Tornado",
        "Hurricane conditions",
        "Tropical storm conditions",
        "Dust",
        "Smoke",
        "Haze",
        "Hot",
        "Cold",
    ],
    ATTR_CONDITION_SNOWY: ["Snow", "Sleet", "Snow/sleet", "Blizzard"],
    ATTR_CONDITION_SNOWY_RAINY: [
        "Rain/snow",
        "Rain/sleet",
        "Freezing rain/snow",
        "Freezing rain",
        "Rain/freezing rain",
    ],
    ATTR_CONDITION_HAIL: [],
    ATTR_CONDITION_LIGHTNING_RAINY: [
        "Thunderstorm (high cloud cover)",
        "Thunderstorm (medium cloud cover)",
        "Thunderstorm (low cloud cover)",
    ],
    ATTR_CONDITION_LIGHTNING: [],
    ATTR_CONDITION_POURING: [],
    ATTR_CONDITION_RAINY: [
        "Rain",
        "Rain showers (high cloud cover)",
        "Rain showers (low cloud cover)",
    ],
    ATTR_CONDITION_WINDY_VARIANT: ["Mostly cloudy and windy", "Overcast and windy"],
    ATTR_CONDITION_WINDY: [
        "Fair/clear and windy",
        "A few clouds and windy",
        "Partly cloudy and windy",
    ],
    ATTR_CONDITION_FOG: ["Fog/mist"],
    "clear": ["Fair/clear"],  # sunny and clear-night
    ATTR_CONDITION_CLOUDY: ["Mostly cloudy", "Overcast"],
    ATTR_CONDITION_PARTLYCLOUDY: ["A few clouds", "Partly cloudy"],
}

DAYNIGHT = "daynight"
HOURLY = "hourly"

NWS_DATA = "nws data"
COORDINATOR_OBSERVATION = "coordinator_observation"
COORDINATOR_FORECAST = "coordinator_forecast"
COORDINATOR_FORECAST_HOURLY = "coordinator_forecast_hourly"

OBSERVATION_VALID_TIME = timedelta(minutes=20)
FORECAST_VALID_TIME = timedelta(minutes=45)


class NWSSensorMetadata(NamedTuple):
    """Sensor metadata for an individual NWS sensor."""

    label: str
    icon: str | None
    device_class: str | None
    unit: str
    unit_convert: str


SENSOR_TYPES: dict[str, NWSSensorMetadata] = {
    "dewpoint": NWSSensorMetadata(
        "Dew Point",
        icon=None,
        device_class=DEVICE_CLASS_TEMPERATURE,
        unit=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    "temperature": NWSSensorMetadata(
        "Temperature",
        icon=None,
        device_class=DEVICE_CLASS_TEMPERATURE,
        unit=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    "windChill": NWSSensorMetadata(
        "Wind Chill",
        icon=None,
        device_class=DEVICE_CLASS_TEMPERATURE,
        unit=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    "heatIndex": NWSSensorMetadata(
        "Heat Index",
        icon=None,
        device_class=DEVICE_CLASS_TEMPERATURE,
        unit=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    "relativeHumidity": NWSSensorMetadata(
        "Relative Humidity",
        icon=None,
        device_class=DEVICE_CLASS_HUMIDITY,
        unit=PERCENTAGE,
        unit_convert=PERCENTAGE,
    ),
    "windSpeed": NWSSensorMetadata(
        "Wind Speed",
        icon="mdi:weather-windy",
        device_class=None,
        unit=SPEED_KILOMETERS_PER_HOUR,
        unit_convert=SPEED_MILES_PER_HOUR,
    ),
    "windGust": NWSSensorMetadata(
        "Wind Gust",
        icon="mdi:weather-windy",
        device_class=None,
        unit=SPEED_KILOMETERS_PER_HOUR,
        unit_convert=SPEED_MILES_PER_HOUR,
    ),
    "windDirection": NWSSensorMetadata(
        "Wind Direction",
        icon="mdi:compass-rose",
        device_class=None,
        unit=DEGREE,
        unit_convert=DEGREE,
    ),
    "barometricPressure": NWSSensorMetadata(
        "Barometric Pressure",
        icon=None,
        device_class=DEVICE_CLASS_PRESSURE,
        unit=PRESSURE_PA,
        unit_convert=PRESSURE_INHG,
    ),
    "seaLevelPressure": NWSSensorMetadata(
        "Sea Level Pressure",
        icon=None,
        device_class=DEVICE_CLASS_PRESSURE,
        unit=PRESSURE_PA,
        unit_convert=PRESSURE_INHG,
    ),
    "visibility": NWSSensorMetadata(
        "Visibility",
        icon="mdi:eye",
        device_class=None,
        unit=LENGTH_METERS,
        unit_convert=LENGTH_MILES,
    ),
}
