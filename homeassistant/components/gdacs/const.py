"""Define constants for the GDACS integration."""
from datetime import timedelta

from aio_georss_gdacs.consts import EVENT_TYPE_MAP

DOMAIN = "gdacs"

PLATFORMS = ("sensor", "geo_location")

FEED = "feed"

CONF_CATEGORIES = "categories"

DEFAULT_ICON = "mdi:alert"
DEFAULT_RADIUS = 500.0
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

# Fetch valid categories from integration library.
VALID_CATEGORIES = list(EVENT_TYPE_MAP.values())
