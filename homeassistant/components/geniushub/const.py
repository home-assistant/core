"""Constants for Genius Hub."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "geniushub"

ATTR_ZONE_MODE = "mode"
ATTR_DURATION = "duration"

SVC_SET_ZONE_MODE = "set_zone_mode"
SVC_SET_ZONE_OVERRIDE = "set_zone_override"

SCAN_INTERVAL = timedelta(seconds=60)

SENSOR_PREFIX = "Genius"

PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
)
