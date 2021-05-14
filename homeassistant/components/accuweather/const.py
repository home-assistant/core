"""Constants for AccuWeather integration."""
from __future__ import annotations

from typing import Final

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
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
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_CUBIC_METER,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_METERS,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_HOURS,
    UV_INDEX,
)

from .model import SensorDescription

ATTRIBUTION: Final = "Data provided by AccuWeather"
ATTR_FORECAST: Final = "forecast"
CONF_FORECAST: Final = "forecast"
COORDINATOR: Final = "coordinator"
DOMAIN: Final = "accuweather"
MANUFACTURER: Final = "AccuWeather, Inc."
NAME: Final = "AccuWeather"
UNDO_UPDATE_LISTENER: Final = "undo_update_listener"

CONDITION_CLASSES: Final[dict[str, list[int]]] = {
    ATTR_CONDITION_CLEAR_NIGHT: [33, 34, 37],
    ATTR_CONDITION_CLOUDY: [7, 8, 38],
    ATTR_CONDITION_EXCEPTIONAL: [24, 30, 31],
    ATTR_CONDITION_FOG: [11],
    ATTR_CONDITION_HAIL: [25],
    ATTR_CONDITION_LIGHTNING: [15],
    ATTR_CONDITION_LIGHTNING_RAINY: [16, 17, 41, 42],
    ATTR_CONDITION_PARTLYCLOUDY: [3, 4, 6, 35, 36],
    ATTR_CONDITION_POURING: [18],
    ATTR_CONDITION_RAINY: [12, 13, 14, 26, 39, 40],
    ATTR_CONDITION_SNOWY: [19, 20, 21, 22, 23, 43, 44],
    ATTR_CONDITION_SNOWY_RAINY: [29],
    ATTR_CONDITION_SUNNY: [1, 2, 5],
    ATTR_CONDITION_WINDY: [32],
}

FORECAST_DAYS: Final[list[int]] = [0, 1, 2, 3, 4]

FORECAST_SENSOR_TYPES: Final[dict[str, SensorDescription]] = {
    "CloudCoverDay": {
        "device_class": None,
        "icon": "mdi:weather-cloudy",
        "label": "Cloud Cover Day",
        "unit_metric": PERCENTAGE,
        "unit_imperial": PERCENTAGE,
    },
    "CloudCoverNight": {
        "device_class": None,
        "icon": "mdi:weather-cloudy",
        "label": "Cloud Cover Night",
        "unit_metric": PERCENTAGE,
        "unit_imperial": PERCENTAGE,
    },
    "Grass": {
        "device_class": None,
        "icon": "mdi:grass",
        "label": "Grass Pollen",
        "unit_metric": CONCENTRATION_PARTS_PER_CUBIC_METER,
        "unit_imperial": CONCENTRATION_PARTS_PER_CUBIC_METER,
    },
    "HoursOfSun": {
        "device_class": None,
        "icon": "mdi:weather-partly-cloudy",
        "label": "Hours Of Sun",
        "unit_metric": TIME_HOURS,
        "unit_imperial": TIME_HOURS,
    },
    "Mold": {
        "device_class": None,
        "icon": "mdi:blur",
        "label": "Mold Pollen",
        "unit_metric": CONCENTRATION_PARTS_PER_CUBIC_METER,
        "unit_imperial": CONCENTRATION_PARTS_PER_CUBIC_METER,
    },
    "Ozone": {
        "device_class": None,
        "icon": "mdi:vector-triangle",
        "label": "Ozone",
        "unit_metric": None,
        "unit_imperial": None,
    },
    "Ragweed": {
        "device_class": None,
        "icon": "mdi:sprout",
        "label": "Ragweed Pollen",
        "unit_metric": CONCENTRATION_PARTS_PER_CUBIC_METER,
        "unit_imperial": CONCENTRATION_PARTS_PER_CUBIC_METER,
    },
    "RealFeelTemperatureMax": {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "label": "RealFeel Temperature Max",
        "unit_metric": TEMP_CELSIUS,
        "unit_imperial": TEMP_FAHRENHEIT,
    },
    "RealFeelTemperatureMin": {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "label": "RealFeel Temperature Min",
        "unit_metric": TEMP_CELSIUS,
        "unit_imperial": TEMP_FAHRENHEIT,
    },
    "RealFeelTemperatureShadeMax": {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "label": "RealFeel Temperature Shade Max",
        "unit_metric": TEMP_CELSIUS,
        "unit_imperial": TEMP_FAHRENHEIT,
    },
    "RealFeelTemperatureShadeMin": {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "label": "RealFeel Temperature Shade Min",
        "unit_metric": TEMP_CELSIUS,
        "unit_imperial": TEMP_FAHRENHEIT,
    },
    "ThunderstormProbabilityDay": {
        "device_class": None,
        "icon": "mdi:weather-lightning",
        "label": "Thunderstorm Probability Day",
        "unit_metric": PERCENTAGE,
        "unit_imperial": PERCENTAGE,
    },
    "ThunderstormProbabilityNight": {
        "device_class": None,
        "icon": "mdi:weather-lightning",
        "label": "Thunderstorm Probability Night",
        "unit_metric": PERCENTAGE,
        "unit_imperial": PERCENTAGE,
    },
    "Tree": {
        "device_class": None,
        "icon": "mdi:tree-outline",
        "label": "Tree Pollen",
        "unit_metric": CONCENTRATION_PARTS_PER_CUBIC_METER,
        "unit_imperial": CONCENTRATION_PARTS_PER_CUBIC_METER,
    },
    "UVIndex": {
        "device_class": None,
        "icon": "mdi:weather-sunny",
        "label": "UV Index",
        "unit_metric": UV_INDEX,
        "unit_imperial": UV_INDEX,
    },
    "WindGustDay": {
        "device_class": None,
        "icon": "mdi:weather-windy",
        "label": "Wind Gust Day",
        "unit_metric": SPEED_KILOMETERS_PER_HOUR,
        "unit_imperial": SPEED_MILES_PER_HOUR,
    },
    "WindGustNight": {
        "device_class": None,
        "icon": "mdi:weather-windy",
        "label": "Wind Gust Night",
        "unit_metric": SPEED_KILOMETERS_PER_HOUR,
        "unit_imperial": SPEED_MILES_PER_HOUR,
    },
    "WindDay": {
        "device_class": None,
        "icon": "mdi:weather-windy",
        "label": "Wind Day",
        "unit_metric": SPEED_KILOMETERS_PER_HOUR,
        "unit_imperial": SPEED_MILES_PER_HOUR,
    },
    "WindNight": {
        "device_class": None,
        "icon": "mdi:weather-windy",
        "label": "Wind Night",
        "unit_metric": SPEED_KILOMETERS_PER_HOUR,
        "unit_imperial": SPEED_MILES_PER_HOUR,
    },
}

OPTIONAL_SENSORS: Final[tuple[str, ...]] = (
    "ApparentTemperature",
    "CloudCover",
    "CloudCoverDay",
    "CloudCoverNight",
    "DewPoint",
    "Grass",
    "Mold",
    "Ozone",
    "Ragweed",
    "RealFeelTemperatureShade",
    "RealFeelTemperatureShadeMax",
    "RealFeelTemperatureShadeMin",
    "Tree",
    "WetBulbTemperature",
    "WindChillTemperature",
    "WindGust",
    "WindGustDay",
    "WindGustNight",
)

SENSOR_TYPES: Final[dict[str, SensorDescription]] = {
    "ApparentTemperature": {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "label": "Apparent Temperature",
        "unit_metric": TEMP_CELSIUS,
        "unit_imperial": TEMP_FAHRENHEIT,
    },
    "Ceiling": {
        "device_class": None,
        "icon": "mdi:weather-fog",
        "label": "Cloud Ceiling",
        "unit_metric": LENGTH_METERS,
        "unit_imperial": LENGTH_FEET,
    },
    "CloudCover": {
        "device_class": None,
        "icon": "mdi:weather-cloudy",
        "label": "Cloud Cover",
        "unit_metric": PERCENTAGE,
        "unit_imperial": PERCENTAGE,
    },
    "DewPoint": {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "label": "Dew Point",
        "unit_metric": TEMP_CELSIUS,
        "unit_imperial": TEMP_FAHRENHEIT,
    },
    "RealFeelTemperature": {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "label": "RealFeel Temperature",
        "unit_metric": TEMP_CELSIUS,
        "unit_imperial": TEMP_FAHRENHEIT,
    },
    "RealFeelTemperatureShade": {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "label": "RealFeel Temperature Shade",
        "unit_metric": TEMP_CELSIUS,
        "unit_imperial": TEMP_FAHRENHEIT,
    },
    "Precipitation": {
        "device_class": None,
        "icon": "mdi:weather-rainy",
        "label": "Precipitation",
        "unit_metric": LENGTH_MILLIMETERS,
        "unit_imperial": LENGTH_INCHES,
    },
    "PressureTendency": {
        "device_class": "accuweather__pressure_tendency",
        "icon": "mdi:gauge",
        "label": "Pressure Tendency",
        "unit_metric": None,
        "unit_imperial": None,
    },
    "UVIndex": {
        "device_class": None,
        "icon": "mdi:weather-sunny",
        "label": "UV Index",
        "unit_metric": UV_INDEX,
        "unit_imperial": UV_INDEX,
    },
    "WetBulbTemperature": {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "label": "Wet Bulb Temperature",
        "unit_metric": TEMP_CELSIUS,
        "unit_imperial": TEMP_FAHRENHEIT,
    },
    "WindChillTemperature": {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "label": "Wind Chill Temperature",
        "unit_metric": TEMP_CELSIUS,
        "unit_imperial": TEMP_FAHRENHEIT,
    },
    "Wind": {
        "device_class": None,
        "icon": "mdi:weather-windy",
        "label": "Wind",
        "unit_metric": SPEED_KILOMETERS_PER_HOUR,
        "unit_imperial": SPEED_MILES_PER_HOUR,
    },
    "WindGust": {
        "device_class": None,
        "icon": "mdi:weather-windy",
        "label": "Wind Gust",
        "unit_metric": SPEED_KILOMETERS_PER_HOUR,
        "unit_imperial": SPEED_MILES_PER_HOUR,
    },
}
