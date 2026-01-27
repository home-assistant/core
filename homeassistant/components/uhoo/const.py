"""Static consts for uhoo integration."""

from datetime import timedelta
import logging

DOMAIN = "uhoo"
PLATFORMS = ["sensor"]
LOGGER = logging.getLogger(__package__)

NAME = "uHoo Integration"
MODEL = "uHoo Indoor Air Monitor"
MANUFACTURER = "uHoo Pte. Ltd."

UPDATE_INTERVAL = timedelta(seconds=300)

API_VIRUS = "virus_index"
API_MOLD = "mold_index"
API_TEMP = "temperature"
API_HUMIDITY = "humidity"
API_PM25 = "pm25"
API_TVOC = "tvoc"
API_CO2 = "co2"
API_CO = "co"
API_PRESSURE = "air_pressure"
API_OZONE = "ozone"
API_NO2 = "no2"
