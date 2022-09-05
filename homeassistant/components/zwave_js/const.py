"""Constants for the Z-Wave JS integration."""
import logging

CONF_ADDON_DEVICE = "device"
CONF_ADDON_EMULATE_HARDWARE = "emulate_hardware"
CONF_ADDON_LOG_LEVEL = "log_level"
CONF_ADDON_NETWORK_KEY = "network_key"
CONF_ADDON_S0_LEGACY_KEY = "s0_legacy_key"
CONF_ADDON_S2_ACCESS_CONTROL_KEY = "s2_access_control_key"
CONF_ADDON_S2_AUTHENTICATED_KEY = "s2_authenticated_key"
CONF_ADDON_S2_UNAUTHENTICATED_KEY = "s2_unauthenticated_key"
CONF_INTEGRATION_CREATED_ADDON = "integration_created_addon"
CONF_NETWORK_KEY = "network_key"
CONF_S0_LEGACY_KEY = "s0_legacy_key"
CONF_S2_ACCESS_CONTROL_KEY = "s2_access_control_key"
CONF_S2_AUTHENTICATED_KEY = "s2_authenticated_key"
CONF_S2_UNAUTHENTICATED_KEY = "s2_unauthenticated_key"
CONF_USB_PATH = "usb_path"
CONF_USE_ADDON = "use_addon"
CONF_DATA_COLLECTION_OPTED_IN = "data_collection_opted_in"
DOMAIN = "zwave_js"

DATA_CLIENT = "client"

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
ATTR_DIRECTION = "direction"
ATTR_EVENT = "event"
ATTR_EVENT_LABEL = "event_label"
ATTR_EVENT_TYPE = "event_type"
ATTR_EVENT_DATA = "event_data"
ATTR_DATA_TYPE = "data_type"
ATTR_WAIT_FOR_RESULT = "wait_for_result"
ATTR_OPTIONS = "options"
ATTR_TEST_NODE_ID = "test_node_id"
ATTR_STATUS = "status"
ATTR_ACKNOWLEDGED_FRAMES = "acknowledged_frames"
ATTR_EVENT_TYPE_LABEL = "event_type_label"
ATTR_DATA_TYPE_LABEL = "data_type_label"

ATTR_NODE = "node"
ATTR_ZWAVE_VALUE = "zwave_value"

# automation trigger attributes
ATTR_PREVIOUS_VALUE = "previous_value"
ATTR_PREVIOUS_VALUE_RAW = "previous_value_raw"
ATTR_CURRENT_VALUE = "current_value"
ATTR_CURRENT_VALUE_RAW = "current_value_raw"
ATTR_DESCRIPTION = "description"
ATTR_EVENT_SOURCE = "event_source"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_PARTIAL_DICT_MATCH = "partial_dict_match"

# service constants
SERVICE_BULK_SET_PARTIAL_CONFIG_PARAMETERS = "bulk_set_partial_config_parameters"
SERVICE_CLEAR_LOCK_USERCODE = "clear_lock_usercode"
SERVICE_INVOKE_CC_API = "invoke_cc_api"
SERVICE_MULTICAST_SET_VALUE = "multicast_set_value"
SERVICE_PING = "ping"
SERVICE_REFRESH_VALUE = "refresh_value"
SERVICE_RESET_METER = "reset_meter"
SERVICE_SET_CONFIG_PARAMETER = "set_config_parameter"
SERVICE_SET_LOCK_USERCODE = "set_lock_usercode"
SERVICE_SET_VALUE = "set_value"

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
ATTR_METER_TYPE_NAME = "meter_type_name"
# invoke CC API
ATTR_METHOD_NAME = "method_name"
ATTR_PARAMETERS = "parameters"

ADDON_SLUG = "core_zwave_js"

# Sensor entity description constants
ENTITY_DESC_KEY_BATTERY = "battery"
ENTITY_DESC_KEY_CURRENT = "current"
ENTITY_DESC_KEY_VOLTAGE = "voltage"
ENTITY_DESC_KEY_ENERGY_MEASUREMENT = "energy_measurement"
ENTITY_DESC_KEY_ENERGY_TOTAL_INCREASING = "energy_total_increasing"
ENTITY_DESC_KEY_POWER = "power"
ENTITY_DESC_KEY_POWER_FACTOR = "power_factor"
ENTITY_DESC_KEY_CO = "co"
ENTITY_DESC_KEY_CO2 = "co2"
ENTITY_DESC_KEY_HUMIDITY = "humidity"
ENTITY_DESC_KEY_ILLUMINANCE = "illuminance"
ENTITY_DESC_KEY_PRESSURE = "pressure"
ENTITY_DESC_KEY_SIGNAL_STRENGTH = "signal_strength"
ENTITY_DESC_KEY_TEMPERATURE = "temperature"
ENTITY_DESC_KEY_TARGET_TEMPERATURE = "target_temperature"
ENTITY_DESC_KEY_MEASUREMENT = "measurement"
ENTITY_DESC_KEY_TOTAL_INCREASING = "total_increasing"

# This API key is only for use with Home Assistant. Reach out to Z-Wave JS to apply for
# your own (https://github.com/zwave-js/firmware-updates/).
API_KEY_FIRMWARE_UPDATE_SERVICE = (
    "55eea74f055bef2ad893348112df6a38980600aaf82d2b02011297fc7ba495f830ca2b70"
)
