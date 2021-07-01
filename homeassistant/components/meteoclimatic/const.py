"""Meteoclimatic component constants."""

from datetime import timedelta

from meteoclimatic import Condition

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
    ATTR_CONDITION_WINDY_VARIANT,
)
from homeassistant.const import (
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)

DOMAIN = "meteoclimatic"
PLATFORMS = ["sensor", "weather"]
ATTRIBUTION = "Data provided by Meteoclimatic"
MODEL = "Meteoclimatic RSS feed"
MANUFACTURER = "Meteoclimatic"

SCAN_INTERVAL = timedelta(minutes=10)

CONF_STATION_CODE = "station_code"

DEFAULT_WEATHER_CARD = True

SENSOR_TYPE_NAME = "name"
SENSOR_TYPE_UNIT = "unit"
SENSOR_TYPE_ICON = "icon"
SENSOR_TYPE_CLASS = "device_class"
SENSOR_TYPES = {
    "temp_current": {
        SENSOR_TYPE_NAME: "Temperature",
        SENSOR_TYPE_UNIT: TEMP_CELSIUS,
        SENSOR_TYPE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    "temp_max": {
        SENSOR_TYPE_NAME: "Daily Max Temperature",
        SENSOR_TYPE_UNIT: TEMP_CELSIUS,
        SENSOR_TYPE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    "temp_min": {
        SENSOR_TYPE_NAME: "Daily Min Temperature",
        SENSOR_TYPE_UNIT: TEMP_CELSIUS,
        SENSOR_TYPE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    "humidity_current": {
        SENSOR_TYPE_NAME: "Humidity",
        SENSOR_TYPE_UNIT: PERCENTAGE,
        SENSOR_TYPE_CLASS: DEVICE_CLASS_HUMIDITY,
    },
    "humidity_max": {
        SENSOR_TYPE_NAME: "Daily Max Humidity",
        SENSOR_TYPE_UNIT: PERCENTAGE,
        SENSOR_TYPE_CLASS: DEVICE_CLASS_HUMIDITY,
    },
    "humidity_min": {
        SENSOR_TYPE_NAME: "Daily Min Humidity",
        SENSOR_TYPE_UNIT: PERCENTAGE,
        SENSOR_TYPE_CLASS: DEVICE_CLASS_HUMIDITY,
    },
    "pressure_current": {
        SENSOR_TYPE_NAME: "Pressure",
        SENSOR_TYPE_UNIT: PRESSURE_HPA,
        SENSOR_TYPE_CLASS: DEVICE_CLASS_PRESSURE,
    },
    "pressure_max": {
        SENSOR_TYPE_NAME: "Daily Max Pressure",
        SENSOR_TYPE_UNIT: PRESSURE_HPA,
        SENSOR_TYPE_CLASS: DEVICE_CLASS_PRESSURE,
    },
    "pressure_min": {
        SENSOR_TYPE_NAME: "Daily Min Pressure",
        SENSOR_TYPE_UNIT: PRESSURE_HPA,
        SENSOR_TYPE_CLASS: DEVICE_CLASS_PRESSURE,
    },
    "wind_current": {
        SENSOR_TYPE_NAME: "Wind Speed",
        SENSOR_TYPE_UNIT: SPEED_KILOMETERS_PER_HOUR,
        SENSOR_TYPE_ICON: "mdi:weather-windy",
    },
    "wind_max": {
        SENSOR_TYPE_NAME: "Daily Max Wind Speed",
        SENSOR_TYPE_UNIT: SPEED_KILOMETERS_PER_HOUR,
        SENSOR_TYPE_ICON: "mdi:weather-windy",
    },
    "wind_bearing": {
        SENSOR_TYPE_NAME: "Wind Bearing",
        SENSOR_TYPE_UNIT: DEGREE,
        SENSOR_TYPE_ICON: "mdi:weather-windy",
    },
    "rain": {
        SENSOR_TYPE_NAME: "Daily Precipitation",
        SENSOR_TYPE_UNIT: LENGTH_MILLIMETERS,
        SENSOR_TYPE_ICON: "mdi:cup-water",
    },
}

CONDITION_CLASSES = {
    ATTR_CONDITION_CLEAR_NIGHT: [Condition.moon, Condition.hazemoon],
    ATTR_CONDITION_CLOUDY: [Condition.mooncloud],
    ATTR_CONDITION_EXCEPTIONAL: [],
    ATTR_CONDITION_FOG: [Condition.fog, Condition.mist],
    ATTR_CONDITION_HAIL: [],
    ATTR_CONDITION_LIGHTNING: [Condition.storm],
    ATTR_CONDITION_LIGHTNING_RAINY: [],
    ATTR_CONDITION_PARTLYCLOUDY: [Condition.suncloud, Condition.hazesun],
    ATTR_CONDITION_POURING: [],
    ATTR_CONDITION_RAINY: [Condition.rain],
    ATTR_CONDITION_SNOWY: [],
    ATTR_CONDITION_SNOWY_RAINY: [],
    ATTR_CONDITION_SUNNY: [Condition.sun],
    ATTR_CONDITION_WINDY: [],
    ATTR_CONDITION_WINDY_VARIANT: [],
}
