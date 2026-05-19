# Shark IQ Constants.

from datetime import timedelta
import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

API_TIMEOUT = 20
UPDATE_INTERVAL = timedelta(seconds=30)
PLATFORMS = [Platform.IMAGE, Platform.SENSOR, Platform.VACUUM]
DOMAIN = "sharkiq"
SHARK = "Shark"
ATTR_ROOMS = "rooms"

SHARKIQ_REGION_EUROPE = "europe"
SHARKIQ_REGION_ELSEWHERE = "elsewhere"
SHARKIQ_REGION_DEFAULT = SHARKIQ_REGION_ELSEWHERE
SHARKIQ_REGION_OPTIONS = [SHARKIQ_REGION_EUROPE, SHARKIQ_REGION_ELSEWHERE]

# API backend identifiers
API_BACKEND_AYLA = "ayla"
API_BACKEND_SKEGOX = "skegox"

# Config entry data keys for token storage
CONF_AUTH0_ID_TOKEN = "auth0_id_token"
CONF_AUTH0_REFRESH_TOKEN = "auth0_refresh_token"
CONF_AUTH0_ACCESS_TOKEN = "auth0_access_token"
CONF_AUTH0_EXPIRY = "auth0_token_expiry"
CONF_AYLA_ACCESS_TOKEN = "ayla_access_token"
CONF_AYLA_REFRESH_TOKEN = "ayla_refresh_token"
CONF_AYLA_TOKEN_EXPIRY = "ayla_token_expiry"
CONF_HOUSEHOLD_ID = "household_id"
CONF_USER_ID = "user_id"
CONF_API_BACKEND = "api_backend"

# Error code descriptions
# Sources: sharkiqlibs/sharkiq, ayla-iot-unofficial, Hubitat SharkIQ driver,
# Domoticz SharkIQ integration, SharkNinja support docs.
ERROR_MESSAGES = {
    0: "No error",
    1: "Side wheel is stuck",
    2: "Side brush is stuck",
    3: "Suction motor failed",
    4: "Brushroll stuck",
    5: "Charging error",  # Inferred — original meaning uncertain, was duplicate of code 1
    6: "Bumper is stuck",
    7: "Cliff sensor is blocked",
    8: "Battery power is low",
    9: "No dustbin",
    10: "Fall sensor is blocked",
    11: "Front wheel is stuck",
    12: "Wrong power adapter",
    13: "Switched off",
    14: "Magnetic strip error",
    16: "Top bumper is stuck",
    18: "Wheel encoder error",
    21: "Boot error",
    23: "Base placement error",
    24: "Critical low battery",
    26: "Dustbin blockage",
    40: "Dustbin is blocked",
}
