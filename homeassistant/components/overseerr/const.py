"""Constants for the Overseerr integration."""

DOMAIN = "overseerr"

DEFAULT_NAME = "Overseerr"
DEFAULT_URL = "http://localhost:5055/api/v1"

SENSOR_TYPES = {
    "movies": {"type": "Movie requests", "icon": "mdi:movie"},
    "tv": {"type": "TV Show requests", "icon": "mdi:television-classic"},
    "pending": {"type": "Pending requests", "icon": "mdi:clock-alert-outline"},
    "approved": {"type": "Approved requests", "icon": "mdi:check"},
    "available": {"type": "Available requests", "icon": "mdi:download"},
    "total": {"type": "Total requests", "icon": "mdi:movie"},
}
