"""Constants for the Z-Wave JS integration."""
import logging

CONF_ADDON_DEVICE = "device"
CONF_ADDON_NETWORK_KEY = "network_key"
CONF_INTEGRATION_CREATED_ADDON = "integration_created_addon"
CONF_NETWORK_KEY = "network_key"
CONF_USB_PATH = "usb_path"
CONF_USE_ADDON = "use_addon"
DOMAIN = "zwave_js"
PLATFORMS = [
    "binary_sensor",
    "climate",
    "cover",
    "fan",
    "light",
    "lock",
    "number",
    "sensor",
    "switch",
]

DATA_CLIENT = "client"
DATA_UNSUBSCRIBE = "unsubs"

EVENT_DEVICE_ADDED_TO_REGISTRY = f"{DOMAIN}_device_added_to_registry"

LOGGER = logging.getLogger(__package__)

# constants for events
ZWAVE_JS_EVENT = f"{DOMAIN}_event"
ATTR_NODE_ID = "node_id"
ATTR_HOME_ID = "home_id"
ATTR_ENDPOINT = "endpoint"
ATTR_LABEL = "label"
ATTR_VALUE = "value"
ATTR_VALUE_RAW = "value_raw"
ATTR_COMMAND_CLASS = "command_class"
ATTR_COMMAND_CLASS_NAME = "command_class_name"
ATTR_TYPE = "type"
ATTR_PROPERTY_NAME = "property_name"
ATTR_PROPERTY_KEY_NAME = "property_key_name"
ATTR_PROPERTY = "property"
ATTR_PROPERTY_KEY = "property_key"
ATTR_PARAMETERS = "parameters"

# service constants
SERVICE_SET_CONFIG_PARAMETER = "set_config_parameter"

ATTR_CONFIG_PARAMETER = "parameter"
ATTR_CONFIG_PARAMETER_BITMASK = "bitmask"
ATTR_CONFIG_VALUE = "value"

SERVICE_REFRESH_VALUE = "refresh_value"

ATTR_REFRESH_ALL_VALUES = "refresh_all_values"

ADDON_SLUG = "core_zwave_js"
