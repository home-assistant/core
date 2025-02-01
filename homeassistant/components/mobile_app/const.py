"""Constants for mobile_app."""

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

DOMAIN = "mobile_app"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CONF_CLOUDHOOK_URL = "cloudhook_url"
CONF_REMOTE_UI_URL = "remote_ui_url"
CONF_SECRET = "secret"
CONF_USER_ID = "user_id"

DATA_CONFIG_ENTRIES = "config_entries"
DATA_DELETED_IDS = "deleted_ids"
DATA_DEVICES = "devices"
DATA_STORE = "store"
DATA_NOTIFY = "notify"
DATA_PUSH_CHANNEL = "push_channel"

ATTR_APP_DATA = "app_data"
ATTR_APP_ID = "app_id"
ATTR_APP_NAME = "app_name"
ATTR_APP_VERSION = "app_version"
ATTR_CONFIG_ENTRY_ID = "entry_id"
ATTR_DEVICE_NAME = "device_name"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"
ATTR_NO_LEGACY_ENCRYPTION = "no_legacy_encryption"
ATTR_OS_NAME = "os_name"
ATTR_OS_VERSION = "os_version"
ATTR_PUSH_WEBSOCKET_CHANNEL = "push_websocket_channel"
ATTR_PUSH_TOKEN = "push_token"
ATTR_PUSH_URL = "push_url"
ATTR_PUSH_RATE_LIMITS = "rateLimits"
ATTR_PUSH_RATE_LIMITS_ERRORS = "errors"
ATTR_PUSH_RATE_LIMITS_MAXIMUM = "maximum"
ATTR_PUSH_RATE_LIMITS_RESETS_AT = "resetsAt"
ATTR_PUSH_RATE_LIMITS_SUCCESSFUL = "successful"
ATTR_SUPPORTS_ENCRYPTION = "supports_encryption"

ATTR_EVENT_DATA = "event_data"
ATTR_EVENT_TYPE = "event_type"

ATTR_TEMPLATE = "template"
ATTR_TEMPLATE_VARIABLES = "variables"

ATTR_SPEED = "speed"
ATTR_ALTITUDE = "altitude"
ATTR_COURSE = "course"
ATTR_VERTICAL_ACCURACY = "vertical_accuracy"

ATTR_WEBHOOK_DATA = "data"
ATTR_WEBHOOK_ENCRYPTED = "encrypted"
ATTR_WEBHOOK_ENCRYPTED_DATA = "encrypted_data"
ATTR_WEBHOOK_ID = "webhook_id"
ATTR_WEBHOOK_TYPE = "type"

ERR_ENCRYPTION_ALREADY_ENABLED = "encryption_already_enabled"
ERR_ENCRYPTION_NOT_AVAILABLE = "encryption_not_available"
ERR_ENCRYPTION_REQUIRED = "encryption_required"
ERR_SENSOR_NOT_REGISTERED = "not_registered"
ERR_INVALID_FORMAT = "invalid_format"


ATTR_SENSOR_ATTRIBUTES = "attributes"
ATTR_SENSOR_DEVICE_CLASS = "device_class"
ATTR_SENSOR_DISABLED = "disabled"
ATTR_SENSOR_ENTITY_CATEGORY = "entity_category"
ATTR_SENSOR_ICON = "icon"
ATTR_SENSOR_NAME = "name"
ATTR_SENSOR_STATE = "state"
ATTR_SENSOR_STATE_CLASS = "state_class"
ATTR_SENSOR_TYPE = "type"
ATTR_SENSOR_TYPE_BINARY_SENSOR = "binary_sensor"
ATTR_SENSOR_TYPE_SENSOR = "sensor"
ATTR_SENSOR_UNIQUE_ID = "unique_id"
ATTR_SENSOR_UOM = "unit_of_measurement"

SIGNAL_SENSOR_UPDATE = f"{DOMAIN}_sensor_update"
SIGNAL_LOCATION_UPDATE = DOMAIN + "_location_update_{}"

ATTR_CAMERA_ENTITY_ID = "camera_entity_id"

SCHEMA_APP_DATA = vol.Schema(
    {
        vol.Inclusive(ATTR_PUSH_TOKEN, "push_cloud"): cv.string,
        vol.Inclusive(ATTR_PUSH_URL, "push_cloud"): cv.url,
        # Set to True to indicate that this registration will connect via websocket channel
        # to receive push notifications.
        vol.Optional(ATTR_PUSH_WEBSOCKET_CHANNEL): cv.boolean,
    },
    extra=vol.ALLOW_EXTRA,
)
