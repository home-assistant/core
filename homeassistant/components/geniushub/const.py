"""Constants for Genius Hub."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "geniushub"

SCAN_INTERVAL = timedelta(seconds=60)

SENSOR_PREFIX = "Genius"

PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
)
