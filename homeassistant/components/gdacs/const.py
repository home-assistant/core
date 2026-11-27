"""Define constants for the GDACS integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "gdacs"

PLATFORMS = [Platform.GEO_LOCATION, Platform.SENSOR]

CONF_CATEGORIES = "categories"

DEFAULT_ICON = "mdi:alert"
DEFAULT_RADIUS = 500000
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
