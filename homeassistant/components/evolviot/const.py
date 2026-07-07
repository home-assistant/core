"""Constants for the EvolvIOT integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "evolviot"
NAME = "EvolvIOT"

DEFAULT_API_BASE_URL = "https://api.evolviot.com/api/homeassistant"
DEFAULT_HEALTH_URL = "https://api.evolviot.com/health"
DEFAULT_LOCAL_COMMAND_TIMEOUT = 3
LOCAL_MDNS_DOMAIN = "evolviot"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = DOMAIN

CONF_ACCESS_TOKEN = "access_token"
CONF_API_BASE_URL = "api_base_url"
CONF_AUTHORIZATION_CODE = "authorization_code"
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_VERIFY_SSL = "verify_ssl"

DATA_API = "api"
DATA_COORDINATOR = "coordinator"
DATA_KNOWN_ENTITIES = "known_entities"

PLATFORMS = (
    Platform.SWITCH,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.FAN,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
)
