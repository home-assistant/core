"""Define constants for the GeoNet NZ Quakes integration."""
from datetime import timedelta

DOMAIN = "geonetnz_quakes"

PLATFORMS = ("sensor", "geo_location")

CONF_MINIMUM_MAGNITUDE = "minimum_magnitude"
CONF_MMI = "mmi"

FEED = "feed"

DEFAULT_FILTER_TIME_INTERVAL = timedelta(days=7)
DEFAULT_MINIMUM_MAGNITUDE = 0.0
DEFAULT_MMI = 3
DEFAULT_RADIUS = 50.0
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

SIGNAL_DELETE_ENTITY = "geonetnz_quakes_delete_{}"
SIGNAL_UPDATE_ENTITY = "geonetnz_quakes_update_{}"
SIGNAL_STATUS = "geonetnz_quakes_status_{}"

SIGNAL_NEW_GEOLOCATION = "geonetnz_quakes_new_geolocation_{}"
