"""Constants for the Ubiquiti airOS integration."""

from datetime import timedelta

from homeassistant.const import Platform

DEFAULT_USERNAME = "ubnt"
DOMAIN = "airos"

SCAN_INTERVAL = timedelta(minutes=1)

MANUFACTURER = "Ubiquiti"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]
