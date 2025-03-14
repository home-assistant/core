"""Constants for the zamg integration."""

from datetime import timedelta
import logging

from homeassistant.const import Platform
from homeassistant.util import dt as dt_util

DOMAIN = "zamg"

PLATFORMS = [Platform.SENSOR, Platform.WEATHER]

LOGGER = logging.getLogger(__package__)

ATTR_STATION = "station"
ATTR_UPDATED = "updated"
ATTRIBUTION = "Data provided by GeoSphere Austria"

CONF_STATION_ID = "station_id"

MANUFACTURER_URL = "https://www.geosphere.at"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
VIENNA_TIME_ZONE = dt_util.get_time_zone("Europe/Vienna")
