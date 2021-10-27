"""Constants for EC component."""
from __future__ import annotations

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEGREE,
    LENGTH_KILOMETERS,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_KPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    UV_INDEX,
)

ATTR_OBSERVATION_TIME = "observation_time"
ATTR_STATION = "station"
CONF_LANGUAGE = "language"
CONF_STATION = "station"
CONF_TITLE = "title"
DOMAIN = "environment_canada"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="condition",
        name="Current Condition",
    ),
    SensorEntityDescription(
        key="dewpoint",
        name="Dew Point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="high_temp",
        name="High Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidex",
        name="Humidex",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="icon_code",
        name="Icon Code",
    ),
    SensorEntityDescription(
        key="low_temp",
        name="Low Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="normal_high",
        name="Normal High Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    SensorEntityDescription(
        key="normal_low",
        name="Normal Low Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    SensorEntityDescription(
        key="pop",
        name="Chance of Precipitation",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="precip_yesterday",
        name="Precipitation Yesterday",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pressure",
        name="Barometric Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_KPA,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tendency",
        name="Tendency",
    ),
    SensorEntityDescription(
        key="text_summary",
        name="Summary",
    ),
    SensorEntityDescription(
        key="timestamp",
        name="Observation Time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="uv_index",
        name="UV Index",
        native_unit_of_measurement=UV_INDEX,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="visibility",
        name="Visibility",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="wind_bearing",
        name="Wind Bearing",
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key="wind_chill",
        name="Wind Chill",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="wind_dir",
        name="Wind Direction",
    ),
    SensorEntityDescription(
        key="wind_gust",
        name="Wind Gust",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="wind_speed",
        name="Wind Speed",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)

ALERT_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="advisories",
        name="Advisory",
        icon="mdi:bell-alert",
    ),
    SensorEntityDescription(
        key="endings",
        name="Endings",
        icon="mdi:alert-circle-check",
    ),
    SensorEntityDescription(
        key="statements",
        name="Statements",
        icon="mdi:bell-alert",
    ),
    SensorEntityDescription(
        key="warnings",
        name="Warnings",
        icon="mdi:alert-octagon",
    ),
    SensorEntityDescription(
        key="watches",
        name="Watches",
        icon="mdi:alert",
    ),
)
