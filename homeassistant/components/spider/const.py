"""Constants for the Spider integration."""
from homeassistant.const import Platform

DOMAIN = "spider"
DEFAULT_SCAN_INTERVAL = 300

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.SWITCH]
