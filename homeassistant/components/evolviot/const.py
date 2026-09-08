"""Constants for the EvolvIOT integration."""

from homeassistant.const import Platform

DOMAIN = "evolviot"
NAME = "EvolvIOT"

DEFAULT_API_BASE_URL = "https://api.evolviot.com/api/homeassistant"

CONF_REFRESH_TOKEN = "refresh_token"

PLATFORMS = (Platform.SWITCH,)
