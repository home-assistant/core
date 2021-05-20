"""Constants for Nettigo Air Monitor integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    PERCENTAGE,
    PRESSURE_HPA,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)

from .model import SensorDescription

ATTR_ENABLED: Final = "enabled"
ATTR_LABEL: Final = "label"
ATTR_UNIT: Final = "unit"

DEFAULT_NAME: Final = "Nettigo Air Monitor"
DEFAULT_UPDATE_INTERVAL: Final = timedelta(minutes=6)
DOMAIN: Final = "nam"
MANUFACTURER: Final = "Nettigo"

SUFFIX_P1: Final = "_p1"
SUFFIX_P2: Final = "_p2"

AIR_QUALITY_SENSORS: Final[dict[str, str]] = {"sds": "SDS011", "sps30": "SPS30"}

SENSORS: Final[dict[str, SensorDescription]] = {
    "bme280_humidity": {
        ATTR_LABEL: f"{DEFAULT_NAME} BME280 Humidity",
        ATTR_UNIT: PERCENTAGE,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_ICON: None,
        ATTR_ENABLED: True,
    },
    "bme280_pressure": {
        ATTR_LABEL: f"{DEFAULT_NAME} BME280 Pressure",
        ATTR_UNIT: PRESSURE_HPA,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        ATTR_ICON: None,
        ATTR_ENABLED: True,
    },
    "bme280_temperature": {
        ATTR_LABEL: f"{DEFAULT_NAME} BME280 Temperature",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_ENABLED: True,
    },
    "bmp280_pressure": {
        ATTR_LABEL: f"{DEFAULT_NAME} BMP280 Pressure",
        ATTR_UNIT: PRESSURE_HPA,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        ATTR_ICON: None,
        ATTR_ENABLED: True,
    },
    "bmp280_temperature": {
        ATTR_LABEL: f"{DEFAULT_NAME} BMP280 Temperature",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_ENABLED: True,
    },
    "heca_humidity": {
        ATTR_LABEL: f"{DEFAULT_NAME} HECA Humidity",
        ATTR_UNIT: PERCENTAGE,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_ICON: None,
        ATTR_ENABLED: True,
    },
    "heca_temperature": {
        ATTR_LABEL: f"{DEFAULT_NAME} HECA Temperature",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_ENABLED: True,
    },
    "sht3x_humidity": {
        ATTR_LABEL: f"{DEFAULT_NAME} SHT3X Humidity",
        ATTR_UNIT: PERCENTAGE,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_ICON: None,
        ATTR_ENABLED: True,
    },
    "sht3x_temperature": {
        ATTR_LABEL: f"{DEFAULT_NAME} SHT3X Temperature",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_ENABLED: True,
    },
    "sps30_p0": {
        ATTR_LABEL: f"{DEFAULT_NAME} SPS30 Particulate Matter 1.0",
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_ENABLED: True,
    },
    "sps30_p4": {
        ATTR_LABEL: f"{DEFAULT_NAME} SPS30 Particulate Matter 4.0",
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_ENABLED: True,
    },
    "humidity": {
        ATTR_LABEL: f"{DEFAULT_NAME} DHT22 Humidity",
        ATTR_UNIT: PERCENTAGE,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_ICON: None,
        ATTR_ENABLED: True,
    },
    "signal": {
        ATTR_LABEL: f"{DEFAULT_NAME} Signal Strength",
        ATTR_UNIT: SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_SIGNAL_STRENGTH,
        ATTR_ICON: None,
        ATTR_ENABLED: False,
    },
    "temperature": {
        ATTR_LABEL: f"{DEFAULT_NAME} DHT22 Temperature",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_ENABLED: True,
    },
    "uptime": {
        ATTR_LABEL: f"{DEFAULT_NAME} Uptime",
        ATTR_UNIT: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
        ATTR_ICON: None,
        ATTR_ENABLED: False,
    },
}
