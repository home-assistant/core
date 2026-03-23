"""Constants for the ESPHome Dashboard integration."""

from datetime import timedelta

DOMAIN = "esphome_dashboard"

# Defaults
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

# ESPHome native API default port (same as esphome.const.DEFAULT_PORT)
DEFAULT_PORT = 6053

# ESPHome changelog base URL
ESPHOME_CHANGELOG_URL = "https://esphome.io/changelog/"
