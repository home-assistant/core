"""IHC component constants."""

from homeassistant.const import Platform

ATTR_IHC_ID = "ihc_id"
ATTR_VALUE = "value"
ATTR_CONTROLLER_ID = "controller_id"

AUTO_SETUP_YAML = "ihc_auto_setup.yaml"

CONF_AUTOSETUP = "auto_setup"
CONF_BINARY_SENSOR = "binary_sensor"
CONF_DIMMABLE = "dimmable"
CONF_INFO = "info"
CONF_INVERTING = "inverting"
CONF_LIGHT = "light"
CONF_NODE = "node"
CONF_NOTE = "note"
CONF_OFF_ID = "off_id"
CONF_ON_ID = "on_id"
CONF_POSITION = "position"
CONF_SENSOR = "sensor"
CONF_SWITCH = "switch"
CONF_XPATH = "xpath"

DOMAIN = "ihc"

IHC_CONTROLLER = "controller"
IHC_CONTROLLER_INDEX = "controller_index"
IHC_PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
)

SERVICE_SET_RUNTIME_VALUE_BOOL = "set_runtime_value_bool"
SERVICE_SET_RUNTIME_VALUE_FLOAT = "set_runtime_value_float"
SERVICE_SET_RUNTIME_VALUE_INT = "set_runtime_value_int"
SERVICE_PULSE = "pulse"
