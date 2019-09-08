"""Define constants for the GeoNet NZ Volcano integration."""
from datetime import timedelta

DOMAIN = "geonetnz_volcano"

PLATFORMS = ("sensor", "geo_location")

FEED = "feed"

DEFAULT_ICON = "mdi:mountain"
DEFAULT_RADIUS = 50.0
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

SIGNAL_DELETE_ENTITY = "geonetnz_volcano_delete_{}"
SIGNAL_UPDATE_ENTITY = "geonetnz_volcano_update_{}"
SIGNAL_STATUS = "geonetnz_volcano_status_{}"

SIGNAL_NEW_GEOLOCATION = "geonetnz_volcano_new_geolocation_{}"
