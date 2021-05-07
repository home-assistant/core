"""Constants for the Geocaching integration."""
from datetime import timedelta

# from homeassistant.components.binary_sensor import (
#     DEVICE_CLASS_CONNECTIVITY,
#     DEVICE_CLASS_PROBLEM,
# )
# from homeassistant.components.sensor import DEVICE_CLASS_POWER, DEVICE_CLASS_TEMPERATURE
from homeassistant.const import (  # ENERGY_KILO_WATT_HOUR,; PERCENTAGE,; POWER_WATT,; TEMP_CELSIUS,
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

# TODO Update with your own urls
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
        ATTR_ICON: None,
        ATTR_DEFAULT_ENABLED: True,
    },
    "find_count": {
        ATTR_NAME: "Total finds",
        ATTR_SECTION: "user",
        ATTR_STATE: "find_count",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: None,
        ATTR_DEFAULT_ENABLED: True,
    },
    "hide_count": {
        ATTR_NAME: "Total hides",
        ATTR_SECTION: "user",
        ATTR_STATE: "hide_count",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: None,
        ATTR_DEFAULT_ENABLED: True,
    },
    "favorite_points": {
        ATTR_NAME: "Favorite points",
        ATTR_SECTION: "user",
        ATTR_STATE: "favorite_points",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: None,
        ATTR_DEFAULT_ENABLED: True,
    },
    "souvenir_count": {
        ATTR_NAME: "Total souvenirs",
        ATTR_SECTION: "user",
        ATTR_STATE: "souvenir_count",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: None,
        ATTR_DEFAULT_ENABLED: True,
    },
    "awarded_favorite_points": {
        ATTR_NAME: "Awarded favorite points",
        ATTR_SECTION: "user",
        ATTR_STATE: "awarded_favorite_points",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: None,
        ATTR_DEFAULT_ENABLED: True,
    },
}
