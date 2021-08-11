"""Constants for the Z-Wave JS integration."""
import logging

CONF_ADDON_DEVICE = "device"
CONF_ADDON_EMULATE_HARDWARE = "emulate_hardware"
CONF_ADDON_LOG_LEVEL = "log_level"
CONF_ADDON_NETWORK_KEY = "network_key"
CONF_INTEGRATION_CREATED_ADDON = "integration_created_addon"
CONF_NETWORK_KEY = "network_key"
CONF_USB_PATH = "usb_path"
CONF_USE_ADDON = "use_addon"
CONF_DATA_COLLECTION_OPTED_IN = "data_collection_opted_in"
DOMAIN = "zwave_js"

DATA_CLIENT = "client"
DATA_PLATFORM_SETUP = "platform_setup"

EVENT_DEVICE_ADDED_TO_REGISTRY = f"{DOMAIN}_device_added_to_registry"

LOGGER = logging.getLogger(__package__)

# constants for events
ZWAVE_JS_VALUE_NOTIFICATION_EVENT = f"{DOMAIN}_value_notification"
ZWAVE_JS_NOTIFICATION_EVENT = f"{DOMAIN}_notification"
ZWAVE_JS_VALUE_UPDATED_EVENT = f"{DOMAIN}_value_updated"
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
ATTR_EVENT = "event"
ATTR_EVENT_LABEL = "event_label"
ATTR_EVENT_TYPE = "event_type"
ATTR_EVENT_DATA = "event_data"
ATTR_DATA_TYPE = "data_type"
ATTR_WAIT_FOR_RESULT = "wait_for_result"
ATTR_OPTIONS = "options"

ATTR_NODE = "node"
ATTR_ZWAVE_VALUE = "zwave_value"

# service constants
SERVICE_SET_VALUE = "set_value"
SERVICE_RESET_METER = "reset_meter"
SERVICE_MULTICAST_SET_VALUE = "multicast_set_value"
SERVICE_PING = "ping"
SERVICE_REFRESH_VALUE = "refresh_value"
SERVICE_SET_CONFIG_PARAMETER = "set_config_parameter"
SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS = "bulk_set_partial_config_parameters"

ATTR_NODES = "nodes"
# config parameter
ATTR_CONFIG_PARAMETER = "parameter"
ATTR_CONFIG_PARAMETER_BITMASK = "bitmask"
ATTR_CONFIG_VALUE = "value"
# refresh value
ATTR_REFRESH_ALL_VALUES = "refresh_all_values"
# multicast
ATTR_BROADCAST = "broadcast"
# meter reset
ATTR_METER_TYPE = "meter_type"

ADDON_SLUG = "core_zwave_js"
