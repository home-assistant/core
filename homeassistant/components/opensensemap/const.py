"""Constants for opensensemap."""
import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

CONF_STATION_ID = "station_id"

DOMAIN = "opensensemap"
MANUFACTURER = "opensensemap.org"

PLATFORMS = [Platform.AIR_QUALITY]
