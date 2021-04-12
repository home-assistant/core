"""Constants for Nettigo Air Monitor integration."""
from datetime import timedelta

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

DEFAULT_NAME = "Nettigo Air Monitor"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=6)
DOMAIN = "nam"
MANUFACTURER = "Nettigo"

AIR_QUALITY_SENSORS = {"sds": "SDS011", "sps30": "SPS30"}

SENSORS = {
    "bme280_humidity": (
        f"{DEFAULT_NAME} BME280 Humidity",
        PERCENTAGE,
        DEVICE_CLASS_HUMIDITY,
        None,
        True,
    ),
    "bme280_pressure": (
        f"{DEFAULT_NAME} BME280 Pressure",
        PRESSURE_HPA,
        DEVICE_CLASS_PRESSURE,
        None,
        True,
    ),
    "bme280_temperature": (
        f"{DEFAULT_NAME} BME280 Temperature",
        TEMP_CELSIUS,
        DEVICE_CLASS_TEMPERATURE,
        None,
        True,
    ),
    "bmp280_pressure": (
        f"{DEFAULT_NAME} BMP280 Pressure",
        PRESSURE_HPA,
        DEVICE_CLASS_PRESSURE,
        None,
        True,
    ),
    "bmp280_temperature": (
        f"{DEFAULT_NAME} BMP280 Temperature",
        TEMP_CELSIUS,
        DEVICE_CLASS_TEMPERATURE,
        None,
        True,
    ),
    "heca_humidity": (
        f"{DEFAULT_NAME} HECA Humidity",
        PERCENTAGE,
        DEVICE_CLASS_HUMIDITY,
        None,
        True,
    ),
    "heca_temperature": (
        f"{DEFAULT_NAME} HECA Temperature",
        TEMP_CELSIUS,
        DEVICE_CLASS_TEMPERATURE,
        None,
        True,
    ),
    "sht3x_humidity": (
        f"{DEFAULT_NAME} SHT3X Humidity",
        PERCENTAGE,
        DEVICE_CLASS_HUMIDITY,
        None,
        True,
    ),
    "sht3x_temperature": (
        f"{DEFAULT_NAME} SHT3X Temperature",
        TEMP_CELSIUS,
        DEVICE_CLASS_TEMPERATURE,
        None,
        True,
    ),
    "sps30_p0": (
        f"{DEFAULT_NAME} SPS30 Particulate Matter 1.0",
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        None,
        "mdi:blur",
        True,
    ),
    "sps30_p4": (
        f"{DEFAULT_NAME} SPS30 Particulate Matter 4.0",
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        None,
        "mdi:blur",
        True,
    ),
    "humidity": (
        f"{DEFAULT_NAME} DHT22 Humidity",
        PERCENTAGE,
        DEVICE_CLASS_HUMIDITY,
        None,
        True,
    ),
    "signal": (
        f"{DEFAULT_NAME} Signal Strength",
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        DEVICE_CLASS_SIGNAL_STRENGTH,
        None,
        False,
    ),
    "temperature": (
        f"{DEFAULT_NAME} DHT22 Temperature",
        TEMP_CELSIUS,
        DEVICE_CLASS_TEMPERATURE,
        None,
        True,
    ),
}
