"""Constants for the Overseerr integration."""

DOMAIN = "overseerr"

DEFAULT_NAME = "Overseerr"
DEFAULT_URL = "http://localhost:5055/api/v1"

SENSOR_TYPES = {
    "movies": {"type": "Movie requests", "icon": "mdi:movie"},
    "tv": {"type": "TV Show requests", "icon": "mdi:television-classic"},
}
