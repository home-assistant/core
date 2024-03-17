"""The Things Network's integration constants."""

CONF_HOSTNAME = "hostname"
CONF_ACCESS_KEY = "access_key"
CONF_APP_ID = "app_id"
CONF_VALUES = "values"
CONF_VALUES_NAME = "name"
CONF_VALUES_UNIT = "unit"

CONF_FOUND_DEVICES = "devices"

DOMAIN = "thethingsnetwork"
TTN_API_HOSTNAME = "eu1.cloud.thethings.network"

DEFAULT_TIMEOUT = 10
DEFAULT_API_REFRESH_PERIOD_S = 5 * 60
DEFAULT_API_REFRESH_PERIOD_S = 30 #TBD remove
DEFAULT_FIRST_FETCH_LAST_H = 48

PLATFORMS = ["sensor"]

# Init menu
OPTIONS_SELECTED_MENU = "selected_menu"
OPTIONS_MENU_EDIT_INTEGRATION = "integration settings"
OPTIONS_MENU_EDIT_DEVICES = "devices"
OPTIONS_MENU_EDIT_FIELDS = "fields"
# Select device menu
OPTIONS_SELECTED_DEVICE = "selected_device"
OPTIONS_SELECTED_FIELD = "selected_field"
# Global settings
OPTIONS_MENU_INTEGRATION_FIRST_FETCH_TIME_H = "first_fetch_time"
OPTIONS_MENU_INTEGRATION_REFRESH_TIME_S = "refresh_time"
# Device settings
OPTIONS_DEVICE_NAME = "name"
# Field settings
OPTIONS_FIELD_NAME = "name"
OPTIONS_FIELD_ENTITY_TYPE = "entity_type"
OPTIONS_FIELD_ENTITY_TYPE_AUTO = "auto"
OPTIONS_FIELD_ENTITY_TYPE_SENSOR = "sensor"
OPTIONS_FIELD_ENTITY_TYPE_BINARY_SENSOR = "binary sensor"
OPTIONS_FIELD_ENTITY_TYPE_DEVICE_TRACKER = "device tracker"
OPTIONS_FIELD_UNIT_MEASUREMENT = "unit_of_measurement"
OPTIONS_FIELD_DEVICE_CLASS = "device_class"
OPTIONS_FIELD_ICON = "icon"
OPTIONS_FIELD_PICTURE = "picture"
OPTIONS_FIELD_SUPPORTED_FEATURES = "supported_features"
OPTIONS_FIELD_CONTEXT_RECENT_TIME_S = "context_recent_time_s"
OPTIONS_FIELD_DEVICE_SCOPE = "device_scope"
OPTIONS_FIELD_DEVICE_SCOPE_GLOBAL = "GLOBAL"


ATTR_DEVICE_ID = "device_id"
ATTR_RAW = "raw"
ATTR_TIME = "time"
