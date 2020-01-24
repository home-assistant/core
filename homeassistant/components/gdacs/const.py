"""Define constants for the GDACS integration."""
from datetime import timedelta

DOMAIN = "gdacs"

PLATFORMS = ("sensor", "geo_location")

FEED = "feed"

CONF_CATEGORIES = "categories"

DEFAULT_ICON = "mdi:alert"
DEFAULT_RADIUS = 500.0
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

SIGNAL_DELETE_ENTITY = "gdacs_delete_{}"
SIGNAL_UPDATE_ENTITY = "gdacs_update_{}"
SIGNAL_STATUS = "gdacs_status_{}"

SIGNAL_NEW_GEOLOCATION = "gdacs_new_geolocation_{}"
