"""Define constants for the Luftdaten component."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)

ATTR_SENSOR_ID = "sensor_id"

CONF_SENSOR_ID = "sensor_id"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

DOMAIN = "luftdaten"


SENSOR_HUMIDITY = "humidity"
SENSOR_PM10 = "P1"
SENSOR_PM2_5 = "P2"
SENSOR_PRESSURE = "pressure"
SENSOR_PRESSURE_AT_SEALEVEL = "pressure_at_sealevel"
SENSOR_TEMPERATURE = "temperature"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=SENSOR_HUMIDITY,
        name="Humidity",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=SENSOR_PRESSURE,
        name="Pressure",
        icon="mdi:arrow-down-bold",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=DEVICE_CLASS_PRESSURE,
    ),
    SensorEntityDescription(
        key=SENSOR_PRESSURE_AT_SEALEVEL,
        name="Pressure at sealevel",
        icon="mdi:download",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=DEVICE_CLASS_PRESSURE,
    ),
    SensorEntityDescription(
        key=SENSOR_PM10,
        name="PM10",
        icon="mdi:thought-bubble",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    SensorEntityDescription(
        key=SENSOR_PM2_5,
        name="PM2.5",
        icon="mdi:thought-bubble-outline",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
)
SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]
