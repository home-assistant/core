"""Constants for zamg the Austrian "Zentralanstalt für Meteorologie und Geodynamik" integration."""

from datetime import timedelta
import logging

from homeassistant.const import Platform
from homeassistant.util import dt as dt_util

DOMAIN = "zamg"

CONF_STATION_ID = "station_id"
PLATFORMS = [Platform.SENSOR, Platform.WEATHER]

LOGGER = logging.getLogger(__package__)

ATTR_STATION = "station"
ATTR_UPDATED = "updated"
ATTRIBUTION = "Data provided by ZAMG"

CONF_STATION_ID = "station_id"

DEFAULT_NAME = "zamg"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
VIENNA_TIME_ZONE = dt_util.get_time_zone("Europe/Vienna")
