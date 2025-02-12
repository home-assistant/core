"""Constants used by the SmartThings component and platforms."""

from datetime import timedelta
import re

DOMAIN = "smartthings"

SCOPES = [
    "r:devices:*",
    "w:devices:*",
    "x:devices:*",
    "r:hubs:*",
    "r:locations:*",
    "w:locations:*",
    "x:locations:*",
    "r:scenes:*",
    "x:scenes:*",
    "r:rules:*",
    "w:rules:*",
    "r:installedapps",
    "w:installedapps",
]

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


IGNORED_CAPABILITIES = [
    "execute",
    "healthCheck",
    "ocf",
]

TOKEN_REFRESH_INTERVAL = timedelta(days=14)

VAL_UID = "^(?:([0-9a-fA-F]{32})|([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}))$"
VAL_UID_MATCHER = re.compile(VAL_UID)
