"""Constants for opensensemap."""
from enum import StrEnum
import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

CONF_STATION_ID = "station_id"

DOMAIN = "opensensemap"
MANUFACTURER = "opensensemap.org"

PLATFORMS = [Platform.AIR_QUALITY]


class SensorTypeId(StrEnum):
    """Sensors as defined in opensensemap-api."""

    PM25 = "PM2.5"
    PM10 = "PM10"
