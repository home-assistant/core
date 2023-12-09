"""Constants for opensensemap."""
from datetime import timedelta
import logging

from homeassistant.const import Platform

CONF_SCAN_INTERVAL_MIN = "scan_interval"
CONF_STATION_ID = "station_id"

DOMAIN = "opensensemap"

LOGGER = logging.getLogger(__package__)
MANUFACTURER = "openSenseMap.org"
PLATFORMS = [Platform.AIR_QUALITY]

SCAN_INTERVAL = timedelta(minutes=10)
