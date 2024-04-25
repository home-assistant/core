"""Constants for Genius Hub."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "geniushub"

SCAN_INTERVAL = timedelta(seconds=60)

DEFAULT_GENIUSHUB_HOST = ""
DEFAULT_GENIISHUB_MAC = ""
DEFAULT_GENIUSHUB_PASSWORD = ""
DEFAULT_GENIISHUB_TOKEN = ""
DEFAULT_GENIUSHUB_USERNAME = ""

SENSOR_PREFIX = "Genius"


PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
)
