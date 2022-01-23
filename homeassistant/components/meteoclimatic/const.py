"""Meteoclimatic component constants."""
from __future__ import annotations

from datetime import timedelta

from meteoclimatic import Condition

from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
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
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    Platform,
)

DOMAIN = "meteoclimatic"
PLATFORMS = [Platform.SENSOR, Platform.WEATHER]
ATTRIBUTION = "Data provided by Meteoclimatic"
MODEL = "Meteoclimatic RSS feed"
MANUFACTURER = "Meteoclimatic"

SCAN_INTERVAL = timedelta(minutes=10)

CONF_STATION_CODE = "station_code"

DEFAULT_WEATHER_CARD = True

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temp_current",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temp_max",
        name="Daily Max Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temp_min",
        name="Daily Min Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="humidity_current",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    SensorEntityDescription(
        key="humidity_max",
        name="Daily Max Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    SensorEntityDescription(
        key="humidity_min",
        name="Daily Min Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    SensorEntityDescription(
        key="pressure_current",
        name="Pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    SensorEntityDescription(
        key="pressure_max",
        name="Daily Max Pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    SensorEntityDescription(
        key="pressure_min",
        name="Daily Min Pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    SensorEntityDescription(
        key="wind_current",
        name="Wind Speed",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        device_class="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="wind_max",
        name="Daily Max Wind Speed",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        device_class="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="wind_bearing",
        name="Wind Bearing",
        native_unit_of_measurement=DEGREE,
        device_class="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="rain",
        name="Daily Precipitation",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        device_class="mdi:cup-water",
    ),
)

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
