"""The rest component constants."""

DOMAIN = "rest"

DEFAULT_METHOD = "GET"
DEFAULT_METHOD_SWITCH = "post"
DEFAULT_VERIFY_SSL = True
DEFAULT_FORCE_UPDATE = False
DEFAULT_ENCODING = "UTF-8"
CONF_ENCODING = "encoding"

DEFAULT_BINARY_SENSOR_NAME = "REST Binary Sensor"
DEFAULT_SENSOR_NAME = "REST Sensor"
CONF_JSON_ATTRS = "json_attributes"
CONF_JSON_ATTRS_PATH = "json_attributes_path"

REST_IDX = "rest_idx"
PLATFORM_IDX = "platform_idx"

COORDINATOR = "coordinator"
REST = "rest"

REST_DATA = "rest_data"

METHODS = ["POST", "GET"]

CONF_STATE_RESOURCE = "state_resource"
DEFAULT_BODY_OFF = "OFF"
DEFAULT_BODY_ON = "ON"
CONF_BODY_OFF = "body_off"
CONF_BODY_ON = "body_on"
CONF_IS_ON_TEMPLATE = "is_on_template"
SUPPORT_REST_METHODS = ["post", "put", "patch"]
