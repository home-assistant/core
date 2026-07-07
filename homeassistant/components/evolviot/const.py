"""Constants for the EvolvIOT integration."""

from datetime import timedelta

from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_VERIFY_SSL,
    Platform,
)

__all__ = [
    "CONF_ACCESS_TOKEN",
    "CONF_CLIENT_ID",
    "CONF_CLIENT_SECRET",
    "CONF_VERIFY_SSL",
]

DOMAIN = "evolviot"
NAME = "EvolvIOT"

DEFAULT_API_BASE_URL = "https://api.evolviot.com/api/homeassistant"
DEFAULT_HEALTH_URL = "https://api.evolviot.com/health"
DEFAULT_LOCAL_COMMAND_TIMEOUT = 3
LOCAL_MDNS_DOMAIN = "evolviot"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = DOMAIN

CONF_API_BASE_URL = "api_base_url"
CONF_AUTHORIZATION_CODE = "authorization_code"
CONF_REFRESH_TOKEN = "refresh_token"

DATA_API = "api"
DATA_COORDINATOR = "coordinator"
DATA_KNOWN_ENTITIES = "known_entities"

PLATFORMS = (Platform.SWITCH,)
