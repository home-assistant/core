"""Support for Ombi."""
from datetime import timedelta

CONF_URLBASE = "urlbase"

DEFAULT_PORT = 5000
DEFAULT_NAME = DOMAIN = "ombi"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_SSL = False
DEFAULT_URLBASE = ""

SENSOR_TYPES = {
    "movies": {"type": "Movie requests", "icon": "mdi:movie"},
    "tv": {"type": "TV show requests", "icon": "mdi:television-classic"},
    "music": {"type": "Music album requests", "icon": "mdi:album"},
    "pending": {"type": "Pending requests", "icon": "mdi:clock-alert-outline"},
    "approved": {"type": "Approved requests", "icon": "mdi:check"},
    "available": {"type": "Available requests", "icon": "mdi:download"},
}
