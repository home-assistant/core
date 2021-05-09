"""Constants for the Geocaching integration."""
from datetime import timedelta

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
)

ATTR_DEFAULT_ENABLED = "default_enabled"
ATTR_MEASUREMENT = "measurement"
DOMAIN = "geocaching"
ATTR_SECTION = "section"

OAUTH2_AUTHORIZE_URL = "https://staging.geocaching.com/oauth/authorize.aspx"
OAUTH2_TOKEN_URL = "https://oauth-staging.geocaching.com/token"
API_ENDPOINT_URL = "https://staging.api.groundspeak.com"

DEFAULT_SCAN_INTERVAL = timedelta(hours=1)

SENSOR_ENTITIES = {
    "username": {
        ATTR_NAME: "Username",
        ATTR_SECTION: "user",
        ATTR_STATE: "username",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:account",
        ATTR_DEFAULT_ENABLED: True,
    },
    "find_count": {
        ATTR_NAME: "Total finds",
        ATTR_SECTION: "user",
        ATTR_STATE: "find_count",
        ATTR_UNIT_OF_MEASUREMENT: "caches",
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:notebook-edit-outline",
        ATTR_DEFAULT_ENABLED: True,
    },
    "hide_count": {
        ATTR_NAME: "Total hides",
        ATTR_SECTION: "user",
        ATTR_STATE: "hide_count",
        ATTR_UNIT_OF_MEASUREMENT: "caches",
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:eye-off-outline",
        ATTR_DEFAULT_ENABLED: True,
    },
    "favorite_points": {
        ATTR_NAME: "Favorite points",
        ATTR_SECTION: "user",
        ATTR_STATE: "favorite_points",
        ATTR_UNIT_OF_MEASUREMENT: "points",
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:heart-outline",
        ATTR_DEFAULT_ENABLED: True,
    },
    "souvenir_count": {
        ATTR_NAME: "Total souvenirs",
        ATTR_SECTION: "user",
        ATTR_STATE: "souvenir_count",
        ATTR_UNIT_OF_MEASUREMENT: "souvenirs",
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:license",
        ATTR_DEFAULT_ENABLED: True,
    },
    "awarded_favorite_points": {
        ATTR_NAME: "Awarded favorite points",
        ATTR_SECTION: "user",
        ATTR_STATE: "awarded_favorite_points",
        ATTR_UNIT_OF_MEASUREMENT: "points",
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:heart",
        ATTR_DEFAULT_ENABLED: True,
    },
}
