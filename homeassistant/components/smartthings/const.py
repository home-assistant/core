"""Constants used by the SmartThings component and platforms."""
from datetime import timedelta
import re

from homeassistant.const import Platform

DOMAIN = "smartthings"

APP_OAUTH_CLIENT_NAME = "Home Assistant"
APP_OAUTH_SCOPES = ["r:devices:*"]
APP_NAME_PREFIX = "homeassistant."

CONF_APP_ID = "app_id"
CONF_CLOUDHOOK_URL = "cloudhook_url"
CONF_INSTALLED_APP_ID = "installed_app_id"
CONF_INSTANCE_ID = "instance_id"
CONF_LOCATION_ID = "location_id"
CONF_REFRESH_TOKEN = "refresh_token"

DATA_MANAGER = "manager"
DATA_BROKERS = "brokers"
EVENT_BUTTON = "smartthings.button"

SIGNAL_SMARTTHINGS_UPDATE = "smartthings_update"
SIGNAL_SMARTAPP_PREFIX = "smartthings_smartap_"

SETTINGS_INSTANCE_ID = "hassInstanceId"

SUBSCRIPTION_WARNING_LIMIT = 40

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

# Ordered 'specific to least-specific platform' in order for capabilities
# to be drawn-down and represented by the most appropriate platform.
PLATFORMS = [
    Platform.CLIMATE,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.COVER,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SCENE,
]

IGNORED_CAPABILITIES = [
    "execute",
    "healthCheck",
    "ocf",
]

TOKEN_REFRESH_INTERVAL = timedelta(days=14)

VAL_UID = "^(?:([0-9a-fA-F]{32})|([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}))$"
VAL_UID_MATCHER = re.compile(VAL_UID)
