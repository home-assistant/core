"""Constants for the solarman integration."""

from homeassistant.const import Platform

DOMAIN = "solarman"
DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = 30
PLATFORMS = [
    Platform.SENSOR,
    Platform.SWITCH,
]
