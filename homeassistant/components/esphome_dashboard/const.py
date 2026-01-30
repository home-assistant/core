"""Constants for the ESPHome Dashboard integration."""

from datetime import timedelta

DOMAIN = "esphome_dashboard"

# Configuration
CONF_URL = "url"

# Defaults
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

# Platforms
PLATFORMS = ["update"]
