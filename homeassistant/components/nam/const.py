"""Constants for Nettigo Air Monitor integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    PRESSURE_HPA,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity import EntityCategory

SUFFIX_P0: Final = "_p0"
SUFFIX_P1: Final = "_p1"
SUFFIX_P2: Final = "_p2"
SUFFIX_P4: Final = "_p4"

ATTR_BME280_HUMIDITY: Final = "bme280_humidity"
ATTR_BME280_PRESSURE: Final = "bme280_pressure"
ATTR_BME280_TEMPERATURE: Final = "bme280_temperature"
ATTR_BMP180_PRESSURE: Final = "bmp180_pressure"
ATTR_BMP180_TEMPERATURE: Final = "bmp180_temperature"
ATTR_BMP280_PRESSURE: Final = "bmp280_pressure"
ATTR_BMP280_TEMPERATURE: Final = "bmp280_temperature"
ATTR_DHT22_HUMIDITY: Final = "dht22_humidity"
ATTR_DHT22_TEMPERATURE: Final = "dht22_temperature"
ATTR_HECA_HUMIDITY: Final = "heca_humidity"
ATTR_HECA_TEMPERATURE: Final = "heca_temperature"
ATTR_MHZ14A_CARBON_DIOXIDE: Final = "mhz14a_carbon_dioxide"
ATTR_SDS011: Final = "sds011"
ATTR_SDS011_P1: Final = f"{ATTR_SDS011}{SUFFIX_P1}"
ATTR_SDS011_P2: Final = f"{ATTR_SDS011}{SUFFIX_P2}"
ATTR_SHT3X_HUMIDITY: Final = "sht3x_humidity"
ATTR_SHT3X_TEMPERATURE: Final = "sht3x_temperature"
ATTR_SIGNAL_STRENGTH: Final = "signal"
ATTR_SPS30: Final = "sps30"
ATTR_SPS30_P0: Final = f"{ATTR_SPS30}{SUFFIX_P0}"
ATTR_SPS30_P1: Final = f"{ATTR_SPS30}{SUFFIX_P1}"
ATTR_SPS30_P2: Final = f"{ATTR_SPS30}{SUFFIX_P2}"
ATTR_SPS30_P4: Final = f"{ATTR_SPS30}{SUFFIX_P4}"
ATTR_UPTIME: Final = "uptime"

DEFAULT_NAME: Final = "Nettigo Air Monitor"
DEFAULT_UPDATE_INTERVAL: Final = timedelta(minutes=6)
DOMAIN: Final = "nam"
MANUFACTURER: Final = "Nettigo"

MIGRATION_SENSORS: Final = [
    ("temperature", ATTR_DHT22_TEMPERATURE),
    ("humidity", ATTR_DHT22_HUMIDITY),
]

SENSORS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key=ATTR_BME280_HUMIDITY,
        name=f"{DEFAULT_NAME} BME280 Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BME280_PRESSURE,
        name=f"{DEFAULT_NAME} BME280 Pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BME280_TEMPERATURE,
        name=f"{DEFAULT_NAME} BME280 Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BMP180_PRESSURE,
        name=f"{DEFAULT_NAME} BMP180 Pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BMP180_TEMPERATURE,
        name=f"{DEFAULT_NAME} BMP180 Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BMP280_PRESSURE,
        name=f"{DEFAULT_NAME} BMP280 Pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BMP280_TEMPERATURE,
        name=f"{DEFAULT_NAME} BMP280 Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_HECA_HUMIDITY,
        name=f"{DEFAULT_NAME} HECA Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_HECA_TEMPERATURE,
        name=f"{DEFAULT_NAME} HECA Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_MHZ14A_CARBON_DIOXIDE,
        name=f"{DEFAULT_NAME} MH-Z14A Carbon Dioxide",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SDS011_P1,
        name=f"{DEFAULT_NAME} SDS011 Particulate Matter 10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SDS011_P2,
        name=f"{DEFAULT_NAME} SDS011 Particulate Matter 2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SHT3X_HUMIDITY,
        name=f"{DEFAULT_NAME} SHT3X Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SHT3X_TEMPERATURE,
        name=f"{DEFAULT_NAME} SHT3X Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SPS30_P0,
        name=f"{DEFAULT_NAME} SPS30 Particulate Matter 1.0",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SPS30_P1,
        name=f"{DEFAULT_NAME} SPS30 Particulate Matter 10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SPS30_P2,
        name=f"{DEFAULT_NAME} SPS30 Particulate Matter 2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SPS30_P4,
        name=f"{DEFAULT_NAME} SPS30 Particulate Matter 4.0",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:molecule",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_DHT22_HUMIDITY,
        name=f"{DEFAULT_NAME} DHT22 Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_DHT22_TEMPERATURE,
        name=f"{DEFAULT_NAME} DHT22 Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SIGNAL_STRENGTH,
        name=f"{DEFAULT_NAME} Signal Strength",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=ATTR_UPTIME,
        name=f"{DEFAULT_NAME} Uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)
