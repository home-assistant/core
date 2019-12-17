"""Yr component constants."""
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)

DOMAIN = "yr"

API_URL = "https://aa015h6buqvih86i1.api.met.no/weatherapi/locationforecast/1.9/"
SYMBOL_API_URL = (
    "https://api.met.no/weatherapi/weathericon/1.1/?symbol={0};content_type=image/png"
)

CONF_FORECAST = "forecast"

DEFAULT_FORECAST = 0
DEFAULT_NAME = "Yr"

SENSOR_TYPE_NAME = "name"
SENSOR_TYPE_UNIT = "unit"
SENSOR_TYPE_CLASS = "device_class"
SENSOR_TYPES = {
    "symbol": {
        SENSOR_TYPE_NAME: "Symbol",
        SENSOR_TYPE_UNIT: None,
        SENSOR_TYPE_CLASS: None,
    },
    "precipitation": {
        SENSOR_TYPE_NAME: "Precipitation",
        SENSOR_TYPE_UNIT: "mm",
        SENSOR_TYPE_CLASS: None,
    },
    "temperature": {
        SENSOR_TYPE_NAME: "Temperature",
        SENSOR_TYPE_UNIT: TEMP_CELSIUS,
        SENSOR_TYPE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    "windSpeed": {
        SENSOR_TYPE_NAME: "Wind speed",
        SENSOR_TYPE_UNIT: "m/s",
        SENSOR_TYPE_CLASS: None,
    },
    "windGust": {
        SENSOR_TYPE_NAME: "Wind gust",
        SENSOR_TYPE_UNIT: "m/s",
        SENSOR_TYPE_CLASS: None,
    },
    "pressure": {
        SENSOR_TYPE_NAME: "Pressure",
        SENSOR_TYPE_UNIT: PRESSURE_HPA,
        SENSOR_TYPE_CLASS: DEVICE_CLASS_PRESSURE,
    },
    "windDirection": {
        SENSOR_TYPE_NAME: "Wind direction",
        SENSOR_TYPE_UNIT: "°",
        SENSOR_TYPE_CLASS: None,
    },
    "humidity": {
        SENSOR_TYPE_NAME: "Humidity",
        SENSOR_TYPE_UNIT: "%",
        SENSOR_TYPE_CLASS: DEVICE_CLASS_HUMIDITY,
    },
    "fog": {SENSOR_TYPE_NAME: "Fog", SENSOR_TYPE_UNIT: "%", SENSOR_TYPE_CLASS: None},
    "cloudiness": {
        SENSOR_TYPE_NAME: "Cloudiness",
        SENSOR_TYPE_UNIT: "%",
        SENSOR_TYPE_CLASS: None,
    },
    "lowClouds": {
        SENSOR_TYPE_NAME: "Low clouds",
        SENSOR_TYPE_UNIT: "%",
        SENSOR_TYPE_CLASS: None,
    },
    "mediumClouds": {
        SENSOR_TYPE_NAME: "Medium clouds",
        SENSOR_TYPE_UNIT: "%",
        SENSOR_TYPE_CLASS: None,
    },
    "highClouds": {
        SENSOR_TYPE_NAME: "High clouds",
        SENSOR_TYPE_UNIT: "%",
        SENSOR_TYPE_CLASS: None,
    },
    "dewpointTemperature": {
        SENSOR_TYPE_NAME: "Dewpoint temperature",
        SENSOR_TYPE_UNIT: TEMP_CELSIUS,
        SENSOR_TYPE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
}
