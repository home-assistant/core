"""Constants for Daikin Onecta."""

from daikin_onecta.client import ONECTA_API_URL

DOMAIN = "daikin_onecta"

OAUTH2_AUTHORIZE = "https://idp.onecta.daikineurope.com/v1/oidc/authorize"
OAUTH2_TOKEN = "https://idp.onecta.daikineurope.com/v1/oidc/token"
DAIKIN_API_URL = ONECTA_API_URL

CONF_HOMEKIT_FAN_MODE_ALIASES = "homekit_fan_mode_aliases"

FANMODE_FIXED = "fixed"
