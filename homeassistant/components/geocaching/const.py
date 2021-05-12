"""Constants for the Geocaching integration."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from .models import GeocachingSensorSettings

DOMAIN = "geocaching"

OAUTH2_AUTHORIZE_URL = "https://staging.geocaching.com/oauth/authorize.aspx"
OAUTH2_TOKEN_URL = "https://oauth-staging.geocaching.com/token"
API_ENDPOINT_URL = "https://staging.api.groundspeak.com"

UPDATE_INTERVAL = timedelta(hours=1)

SENSOR_DATA: Final[dict[str, GeocachingSensorSettings]] = {
    "username": {
        "name": "Username",
        "section": "user",
        "state": "username",
        "unit_of_measurement": None,
        "device_class": None,
        "icon": "mdi:account",
        "default_enabled": False,
    },
    "find_count": {
        "name": "Total finds",
        "section": "user",
        "state": "find_count",
        "unit_of_measurement": "caches",
        "device_class": None,
        "icon": "mdi:notebook-edit-outline",
        "default_enabled": True,
    },
    "hide_count": {
        "name": "Total hides",
        "section": "user",
        "state": "hide_count",
        "unit_of_measurement": "caches",
        "device_class": None,
        "icon": "mdi:eye-off-outline",
        "default_enabled": True,
    },
    "favorite_points": {
        "name": "Favorite points",
        "section": "user",
        "state": "favorite_points",
        "unit_of_measurement": "points",
        "device_class": None,
        "icon": "mdi:heart-outline",
        "default_enabled": True,
    },
    "souvenir_count": {
        "name": "Total souvenirs",
        "section": "user",
        "state": "souvenir_count",
        "unit_of_measurement": "souvenirs",
        "device_class": None,
        "icon": "mdi:license",
        "default_enabled": True,
    },
    "awarded_favorite_points": {
        "name": "Awarded favorite points",
        "section": "user",
        "state": "awarded_favorite_points",
        "unit_of_measurement": "points",
        "device_class": None,
        "icon": "mdi:heart",
        "default_enabled": True,
    },
}
