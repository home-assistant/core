"""Constants used by the SmartThings component and platforms."""
import re

APP_OAUTH_SCOPES = [
    'r:devices:*'
]
APP_NAME_PREFIX = 'homeassistant.'
CONF_APP_ID = 'app_id'
CONF_INSTALLED_APP_ID = 'installed_app_id'
CONF_INSTANCE_ID = 'instance_id'
CONF_LOCATION_ID = 'location_id'
DATA_MANAGER = 'manager'
DATA_BROKERS = 'brokers'
DOMAIN = 'smartthings'
EVENT_BUTTON = "smartthings.button"
SIGNAL_SMARTTHINGS_UPDATE = 'smartthings_update'
SIGNAL_SMARTAPP_PREFIX = 'smartthings_smartap_'
SETTINGS_INSTANCE_ID = "hassInstanceId"
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
# Ordered 'specific to least-specific platform' in order for capabilities
# to be drawn-down and represented by the appropriate platform.
SUPPORTED_PLATFORMS = [
    'climate',
    'fan',
    'light',
    'lock',
    'switch',
    'binary_sensor',
    'sensor'
]
VAL_UID = "^(?:([0-9a-fA-F]{32})|([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]" \
          "{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}))$"
VAL_UID_MATCHER = re.compile(VAL_UID)
