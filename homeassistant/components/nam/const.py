"""Constants for Nettigo Air Monitor integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

SUFFIX_CAQI: Final = "_caqi"
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
ATTR_SDS011_CAQI: Final = f"{ATTR_SDS011}{SUFFIX_CAQI}"
ATTR_SDS011_CAQI_LEVEL: Final = f"{ATTR_SDS011}{SUFFIX_CAQI}_level"
ATTR_SDS011_P1: Final = f"{ATTR_SDS011}{SUFFIX_P1}"
ATTR_SDS011_P2: Final = f"{ATTR_SDS011}{SUFFIX_P2}"
ATTR_SHT3X_HUMIDITY: Final = "sht3x_humidity"
ATTR_SHT3X_TEMPERATURE: Final = "sht3x_temperature"
ATTR_SIGNAL_STRENGTH: Final = "signal"
ATTR_SPS30: Final = "sps30"
ATTR_SPS30_CAQI: Final = f"{ATTR_SPS30}{SUFFIX_CAQI}"
ATTR_SPS30_CAQI_LEVEL: Final = f"{ATTR_SPS30}{SUFFIX_CAQI}_level"
ATTR_SPS30_P0: Final = f"{ATTR_SPS30}{SUFFIX_P0}"
ATTR_SPS30_P1: Final = f"{ATTR_SPS30}{SUFFIX_P1}"
ATTR_SPS30_P2: Final = f"{ATTR_SPS30}{SUFFIX_P2}"
ATTR_SPS30_P4: Final = f"{ATTR_SPS30}{SUFFIX_P4}"
ATTR_UPTIME: Final = "uptime"

DEFAULT_UPDATE_INTERVAL: Final = timedelta(minutes=6)
DOMAIN: Final = "nam"
MANUFACTURER: Final = "Nettigo"

MIGRATION_SENSORS: Final = [
    ("temperature", ATTR_DHT22_TEMPERATURE),
    ("humidity", ATTR_DHT22_HUMIDITY),
]
