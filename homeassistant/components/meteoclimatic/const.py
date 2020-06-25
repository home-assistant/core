"""Meteoclimatic component constants."""

from datetime import timedelta

from meteoclimatic import Condition

from homeassistant.const import (
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)

DOMAIN = "meteoclimatic"
PLATFORMS = ["sensor", "weather"]
ATTRIBUTION = "Data provided by Meteoclimatic"

SCAN_INTERVAL = timedelta(minutes=5)

CONF_STATION_CODE = "station_code"

METEOCLIMATIC_UPDATER = "meteoclimatic_updater"
METEOCLIMATIC_COORDINATOR = "meteoclimatic_coordinator"
METEOCLIMATIC_STATION_CODE = "meteoclimatic_station_code"
METEOCLIMATIC_STATION_NAME = "meteoclimatic_station_name"

DEFAULT_WEATHER_CARD = True

SENSOR_TYPE_NAME = "name"
SENSOR_TYPE_UNIT = "unit"
SENSOR_TYPE_ICON = "icon"
SENSOR_TYPE_CLASS = "device_class"
SENSOR_TYPES = {
    "temp_current": {
        SENSOR_TYPE_NAME: "Temperature",
        SENSOR_TYPE_UNIT: TEMP_CELSIUS,
        SENSOR_TYPE_ICON: "mdi:thermometer",
        SENSOR_TYPE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    "temp_max": {
        SENSOR_TYPE_NAME: "Max Temp.",
        SENSOR_TYPE_UNIT: TEMP_CELSIUS,
        SENSOR_TYPE_ICON: "mdi:thermometer",
        SENSOR_TYPE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    "temp_min": {
        SENSOR_TYPE_NAME: "Min Temp.",
        SENSOR_TYPE_UNIT: TEMP_CELSIUS,
        SENSOR_TYPE_ICON: "mdi:thermometer",
        SENSOR_TYPE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    "humidity_current": {
        SENSOR_TYPE_NAME: "Humidity",
        SENSOR_TYPE_UNIT: UNIT_PERCENTAGE,
        SENSOR_TYPE_ICON: "mdi:water-percent",
        SENSOR_TYPE_CLASS: DEVICE_CLASS_HUMIDITY,
    },
    "humidity_max": {
        SENSOR_TYPE_NAME: "Max Humidity",
        SENSOR_TYPE_UNIT: UNIT_PERCENTAGE,
        SENSOR_TYPE_ICON: "mdi:water-percent",
        SENSOR_TYPE_CLASS: DEVICE_CLASS_HUMIDITY,
    },
    "humidity_min": {
        SENSOR_TYPE_NAME: "Min Humidity",
        SENSOR_TYPE_UNIT: UNIT_PERCENTAGE,
        SENSOR_TYPE_ICON: "mdi:water-percent",
        SENSOR_TYPE_CLASS: DEVICE_CLASS_HUMIDITY,
    },
    "pressure_current": {
        SENSOR_TYPE_NAME: "Pressure",
        SENSOR_TYPE_UNIT: PRESSURE_HPA,
        SENSOR_TYPE_ICON: "mdi:gauge",
        SENSOR_TYPE_CLASS: DEVICE_CLASS_PRESSURE,
    },
    "pressure_max": {
        SENSOR_TYPE_NAME: "Max Pressure",
        SENSOR_TYPE_UNIT: PRESSURE_HPA,
        SENSOR_TYPE_ICON: "mdi:gauge",
        SENSOR_TYPE_CLASS: DEVICE_CLASS_PRESSURE,
    },
    "pressure_min": {
        SENSOR_TYPE_NAME: "Min Pressure",
        SENSOR_TYPE_UNIT: PRESSURE_HPA,
        SENSOR_TYPE_ICON: "mdi:gauge",
        SENSOR_TYPE_CLASS: DEVICE_CLASS_PRESSURE,
    },
    "wind_current": {
        SENSOR_TYPE_NAME: "Wind Speed",
        SENSOR_TYPE_UNIT: SPEED_KILOMETERS_PER_HOUR,
        SENSOR_TYPE_ICON: "mdi:weather-windy",
        SENSOR_TYPE_CLASS: None,
    },
    "wind_max": {
        SENSOR_TYPE_NAME: "Max Wind Speed",
        SENSOR_TYPE_UNIT: SPEED_KILOMETERS_PER_HOUR,
        SENSOR_TYPE_ICON: "mdi:weather-windy",
        SENSOR_TYPE_CLASS: None,
    },
    "wind_bearing": {
        SENSOR_TYPE_NAME: "Wind Bearing",
        SENSOR_TYPE_UNIT: DEGREE,
        SENSOR_TYPE_ICON: "mdi:weather-windy",
        SENSOR_TYPE_CLASS: None,
    },
    "rain": {
        SENSOR_TYPE_NAME: "Rain",
        SENSOR_TYPE_UNIT: "mm",
        SENSOR_TYPE_ICON: "mdi:weather-rainy",
        SENSOR_TYPE_CLASS: None,
    },
}

CONDITION_CLASSES = {
    "clear-night": [Condition.moon, Condition.hazemoon],
    "cloudy": [Condition.mooncloud],
    "fog": [Condition.fog, Condition.mist],
    "hail": [],
    "lightning": [Condition.storm],
    "lightning-rainy": [],
    "partlycloudy": [Condition.suncloud, Condition.hazesun],
    "pouring": [],
    "rainy": [Condition.rain],
    "snowy": [],
    "snowy-rainy": [],
    "sunny": [Condition.sun],
    "windy": [],
    "windy-variant": [],
    "exceptional": [],
}
