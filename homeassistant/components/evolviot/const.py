"""Constants for the EvolvIOT integration."""

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_VERIFY_SSL, Platform

__all__ = [
    "CONF_ACCESS_TOKEN",
    "CONF_VERIFY_SSL",
]

DOMAIN = "evolviot"
NAME = "EvolvIOT"

DEFAULT_API_BASE_URL = "https://api.evolviot.com/api/homeassistant"

CONF_API_BASE_URL = "api_base_url"
CONF_REFRESH_TOKEN = "refresh_token"

PLATFORMS = (Platform.SWITCH,)
