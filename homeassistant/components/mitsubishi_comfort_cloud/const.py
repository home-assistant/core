"""Constants for Mitsubishi Comfort Cloud."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "mitsubishi_comfort_cloud"
PLATFORMS = [Platform.CLIMATE]
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
