"""Constants used by the SmartThings component and platforms."""

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
    "sse",
]

CONF_APP_ID = "app_id"
CONF_CLOUDHOOK_URL = "cloudhook_url"
CONF_INSTALLED_APP_ID = "installed_app_id"
CONF_INSTANCE_ID = "instance_id"
CONF_LOCATION_ID = "location_id"
CONF_REFRESH_TOKEN = "refresh_token"

MAIN = "main"
OLD_DATA = "old_data"
