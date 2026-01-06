"""Imports for const.py."""

from datetime import timedelta
import logging

DOMAIN = "uhoo"
LOGGER = logging.getLogger(__package__)
APP_VERSION: int = 1

# Base component constants
NAME = "uHoo Integration"
MODEL = "uHoo Indoor Air Monitor"
MANUFACTURER = "uHoo, Inc."
VERSION = "1.0.0"
ISSUE_URL = "https://github.com/getuhoo/uhooair-homeassistant/issues"

UPDATE_INTERVAL = timedelta(seconds=300)

PLATFORMS = ["sensor"]

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

ATTR_LABEL = "label"
ATTR_UNIQUE_ID = "unique_id"
