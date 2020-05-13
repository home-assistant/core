"""Define constants for the GeoNet NZ Volcano integration."""
from datetime import timedelta

DOMAIN = "geonetnz_volcano"

FEED = "feed"

ATTR_ACTIVITY = "activity"
ATTR_DISTANCE = "distance"
ATTR_EXTERNAL_ID = "external_id"
ATTR_HAZARDS = "hazards"

# Icon alias "mdi:mountain" not working.
DEFAULT_ICON = "mdi:image-filter-hdr"
DEFAULT_RADIUS = 50.0
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
