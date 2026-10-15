"""Constants for the Tank Utility integration."""

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "tank_utility"
LOGGER = logging.getLogger(__package__)

DEFAULT_SCAN_INTERVAL = timedelta(hours=1)
PLATFORMS: list[Platform] = [Platform.SENSOR]

SENSOR_TYPE = "tank"
SENSOR_ROUNDING_PRECISION = 1
SENSOR_ATTRS = [
    "name",
    "address",
    "capacity",
    "fuelType",
    "orientation",
    "status",
    "time",
    "time_iso",
]
