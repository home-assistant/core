"""Constants for Nettigo Air Monitor integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    PRESSURE_HPA,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)

from .model import SensorDescription

DEFAULT_NAME: Final = "Nettigo Air Monitor"
DEFAULT_UPDATE_INTERVAL: Final = timedelta(minutes=6)
DOMAIN: Final = "nam"
MANUFACTURER: Final = "Nettigo"

SUFFIX_P1: Final = "_p1"
SUFFIX_P2: Final = "_p2"

AIR_QUALITY_SENSORS: Final[dict[str, str]] = {"sds": "SDS011", "sps30": "SPS30"}

SENSORS: Final[dict[str, SensorDescription]] = {
    "bme280_humidity": {
        "label": f"{DEFAULT_NAME} BME280 Humidity",
        "unit": PERCENTAGE,
        "device_class": DEVICE_CLASS_HUMIDITY,
        "icon": None,
        "enabled": True,
    },
    "bme280_pressure": {
        "label": f"{DEFAULT_NAME} BME280 Pressure",
        "unit": PRESSURE_HPA,
        "device_class": DEVICE_CLASS_PRESSURE,
        "icon": None,
        "enabled": True,
    },
    "bme280_temperature": {
        "label": f"{DEFAULT_NAME} BME280 Temperature",
        "unit": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "enabled": True,
    },
    "bmp280_pressure": {
        "label": f"{DEFAULT_NAME} BMP280 Pressure",
        "unit": PRESSURE_HPA,
        "device_class": DEVICE_CLASS_PRESSURE,
        "icon": None,
        "enabled": True,
    },
    "bmp280_temperature": {
        "label": f"{DEFAULT_NAME} BMP280 Temperature",
        "unit": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "enabled": True,
    },
    "heca_humidity": {
        "label": f"{DEFAULT_NAME} HECA Humidity",
        "unit": PERCENTAGE,
        "device_class": DEVICE_CLASS_HUMIDITY,
        "icon": None,
        "enabled": True,
    },
    "heca_temperature": {
        "label": f"{DEFAULT_NAME} HECA Temperature",
        "unit": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "enabled": True,
    },
    "sht3x_humidity": {
        "label": f"{DEFAULT_NAME} SHT3X Humidity",
        "unit": PERCENTAGE,
        "device_class": DEVICE_CLASS_HUMIDITY,
        "icon": None,
        "enabled": True,
    },
    "sht3x_temperature": {
        "label": f"{DEFAULT_NAME} SHT3X Temperature",
        "unit": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "enabled": True,
    },
    "sps30_p0": {
        "label": f"{DEFAULT_NAME} SPS30 Particulate Matter 1.0",
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "device_class": None,
        "icon": "mdi:blur",
        "enabled": True,
    },
    "sps30_p4": {
        "label": f"{DEFAULT_NAME} SPS30 Particulate Matter 4.0",
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "device_class": None,
        "icon": "mdi:blur",
        "enabled": True,
    },
    "humidity": {
        "label": f"{DEFAULT_NAME} DHT22 Humidity",
        "unit": PERCENTAGE,
        "device_class": DEVICE_CLASS_HUMIDITY,
        "icon": None,
        "enabled": True,
    },
    "signal": {
        "label": f"{DEFAULT_NAME} Signal Strength",
        "unit": SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        "device_class": DEVICE_CLASS_SIGNAL_STRENGTH,
        "icon": None,
        "enabled": False,
    },
    "temperature": {
        "label": f"{DEFAULT_NAME} DHT22 Temperature",
        "unit": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "enabled": True,
    },
}
