"""Constants for the Geocaching integration."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final

from homeassistant.const import (
    ATTR_ICON,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
)

if TYPE_CHECKING:
    from .models import GeocachingSensorSettings

DOMAIN = "geocaching"

OAUTH2_AUTHORIZE_URL = "https://staging.geocaching.com/oauth/authorize.aspx"
OAUTH2_TOKEN_URL = "https://oauth-staging.geocaching.com/token"
API_ENDPOINT_URL = "https://staging.api.groundspeak.com"

UPDATE_INTERVAL = timedelta(hours=1)

ATTR_DEFAULT_ENABLED: Final = "default_enabled"
ATTR_SECTION: Final = "section"

SENSOR_DATA: Final[dict[str, GeocachingSensorSettings]] = {
    "username": {
        ATTR_NAME: "Username",
        ATTR_SECTION: "user",
        ATTR_STATE: "username",
        ATTR_ICON: "mdi:account",
        ATTR_DEFAULT_ENABLED: False,
    },
    "find_count": {
        ATTR_NAME: "Total finds",
        ATTR_SECTION: "user",
        ATTR_STATE: "find_count",
        ATTR_UNIT_OF_MEASUREMENT: "caches",
        ATTR_ICON: "mdi:notebook-edit-outline",
    },
    "hide_count": {
        ATTR_NAME: "Total hides",
        ATTR_SECTION: "user",
        ATTR_STATE: "hide_count",
        ATTR_UNIT_OF_MEASUREMENT: "caches",
        ATTR_ICON: "mdi:eye-off-outline",
    },
    "favorite_points": {
        ATTR_NAME: "Favorite points",
        ATTR_SECTION: "user",
        ATTR_STATE: "favorite_points",
        ATTR_UNIT_OF_MEASUREMENT: "points",
        ATTR_ICON: "mdi:heart-outline",
    },
    "souvenir_count": {
        ATTR_NAME: "Total souvenirs",
        ATTR_SECTION: "user",
        ATTR_STATE: "souvenir_count",
        ATTR_UNIT_OF_MEASUREMENT: "souvenirs",
        ATTR_ICON: "mdi:license",
    },
    "awarded_favorite_points": {
        ATTR_NAME: "Awarded favorite points",
        ATTR_SECTION: "user",
        ATTR_STATE: "awarded_favorite_points",
        ATTR_UNIT_OF_MEASUREMENT: "points",
        ATTR_ICON: "mdi:heart",
    },
}
