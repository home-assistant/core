"""Constants for the Z-Wave JS integration."""

from enum import StrEnum
import logging

from awesomeversion import AwesomeVersion
from zwave_js_server.const.command_class.window_covering import (
    WindowCoveringPropertyKey,
)

from homeassistant.const import APPLICATION_NAME, __version__ as HA_VERSION

LR_ADDON_VERSION = AwesomeVersion("0.5.0")
ESPHOME_ADDON_VERSION = AwesomeVersion("0.24.0")

USER_AGENT = {APPLICATION_NAME: HA_VERSION}

CONF_ADDON_DEVICE = "device"
CONF_ADDON_NETWORK_KEY = "network_key"
CONF_ADDON_S0_LEGACY_KEY = "s0_legacy_key"
CONF_ADDON_S2_ACCESS_CONTROL_KEY = "s2_access_control_key"
CONF_ADDON_S2_AUTHENTICATED_KEY = "s2_authenticated_key"
CONF_ADDON_S2_UNAUTHENTICATED_KEY = "s2_unauthenticated_key"
CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY = "lr_s2_access_control_key"
CONF_ADDON_LR_S2_AUTHENTICATED_KEY = "lr_s2_authenticated_key"
CONF_ADDON_SOCKET = "socket"
CONF_INTEGRATION_CREATED_ADDON = "integration_created_addon"
CONF_NETWORK_KEY = "network_key"
CONF_S0_LEGACY_KEY = "s0_legacy_key"
CONF_S2_ACCESS_CONTROL_KEY = "s2_access_control_key"
CONF_S2_AUTHENTICATED_KEY = "s2_authenticated_key"
CONF_S2_UNAUTHENTICATED_KEY = "s2_unauthenticated_key"
CONF_LR_S2_ACCESS_CONTROL_KEY = "lr_s2_access_control_key"
CONF_LR_S2_AUTHENTICATED_KEY = "lr_s2_authenticated_key"
CONF_SOCKET_PATH = "socket_path"
CONF_USB_PATH = "usb_path"
CONF_USE_ADDON = "use_addon"
CONF_DATA_COLLECTION_OPTED_IN = "data_collection_opted_in"
DOMAIN = "zwave_js"


EVENT_DEVICE_ADDED_TO_REGISTRY = f"{DOMAIN}_device_added_to_registry"
EVENT_VALUE_ADDED = "value added"
EVENT_VALUE_REMOVED = "value removed"
EVENT_VALUE_UPDATED = "value updated"
EVENT_METADATA_UPDATED = "metadata updated"

LOGGER = logging.getLogger(__package__)
LIB_LOGGER = logging.getLogger("zwave_js_server")

# constants extra state attributes
ATTR_RESERVED_VALUES = "reserved_values"  # ConfigurationValue number entities

# constants for events
ZWAVE_JS_VALUE_NOTIFICATION_EVENT = f"{DOMAIN}_value_notification"
ZWAVE_JS_NOTIFICATION_EVENT = f"{DOMAIN}_notification"
ZWAVE_JS_VALUE_UPDATED_EVENT = f"{DOMAIN}_value_updated"
ATTR_NODE_ID = "node_id"
ATTR_HOME_ID = "home_id"
ATTR_HOME_ID_HEX = "home_id_hex"
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
ATTR_URGENCY = "urgency"
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
ATTR_PARTIAL_DICT_MATCH = "partial_dict_match"

# credential type string values
CREDENTIAL_TYPE_BLE = "ble"
CREDENTIAL_TYPE_DESFIRE = "desfire"
CREDENTIAL_TYPE_EYE_BIOMETRIC = "eye_biometric"
CREDENTIAL_TYPE_FACE_BIOMETRIC = "face_biometric"
CREDENTIAL_TYPE_FINGER_BIOMETRIC = "finger_biometric"
CREDENTIAL_TYPE_HAND_BIOMETRIC = "hand_biometric"
CREDENTIAL_TYPE_NFC = "nfc"
CREDENTIAL_TYPE_PASSWORD = "password"
CREDENTIAL_TYPE_PIN_CODE = "pin_code"
CREDENTIAL_TYPE_RFID_CODE = "rfid_code"
CREDENTIAL_TYPE_UNSPECIFIED_BIOMETRIC = "unspecified_biometric"
CREDENTIAL_TYPE_UWB = "uwb"

# writable credential types (for set/clear services)
WRITABLE_CREDENTIAL_TYPES = {CREDENTIAL_TYPE_PIN_CODE, CREDENTIAL_TYPE_PASSWORD}

# user type string values
USER_TYPE_GENERAL = "general"
USER_TYPE_PROGRAMMING = "programming"
USER_TYPE_NON_ACCESS = "non_access"
USER_TYPE_DURESS = "duress"
USER_TYPE_DISPOSABLE = "disposable"
USER_TYPE_EXPIRING = "expiring"
USER_TYPE_REMOTE_ONLY = "remote_only"

# credential rule string values
CREDENTIAL_RULE_SINGLE = "single"
CREDENTIAL_RULE_DUAL = "dual"
CREDENTIAL_RULE_TRIPLE = "triple"

# config parameter
ATTR_CONFIG_PARAMETER = "parameter"
ATTR_CONFIG_PARAMETER_BITMASK = "bitmask"
# refresh value
ATTR_REFRESH_ALL_VALUES = "refresh_all_values"
# meter reset
ATTR_METER_TYPE = "meter_type"
ATTR_METER_TYPE_NAME = "meter_type_name"
# invoke CC API
ATTR_METHOD_NAME = "method_name"
ATTR_PARAMETERS = "parameters"
ADDON_SLUG = "core_zwave_js"

NODE_STATUSES = ["asleep", "awake", "dead", "alive"]

# Sensor entity description constants
ENTITY_DESC_KEY_BATTERY_LIST_STATE = "battery_list_state"
ENTITY_DESC_KEY_BATTERY_MAXIMUM_CAPACITY = "battery_maximum_capacity"
ENTITY_DESC_KEY_BATTERY_TEMPERATURE = "battery_temperature"
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
ENTITY_DESC_KEY_TARGET_TEMPERATURE = "target_temperature"
ENTITY_DESC_KEY_UV_INDEX = "uv_index"
ENTITY_DESC_KEY_MEASUREMENT = "measurement"
ENTITY_DESC_KEY_TOTAL_INCREASING = "total_increasing"

ENTITY_DESC_KEY_ENERGY_PRODUCTION_TIME = "energy_production_time"
ENTITY_DESC_KEY_ENERGY_PRODUCTION_TOTAL = "energy_production_total"
ENTITY_DESC_KEY_ENERGY_PRODUCTION_TODAY = "energy_production_today"

# This API key is only for use with Home Assistant. Reach out to Z-Wave JS to apply for
# your own (https://github.com/zwave-js/firmware-updates/).
API_KEY_FIRMWARE_UPDATE_SERVICE = (
    "2e39d98fc56386389fbb35e5a98fa1b44b9fdd8f971460303587cff408430d4cfcde6134"
)

# Platform constants
# cover
COVER_POSITION_PROPERTY_KEYS: set[str | int | None] = {
    WindowCoveringPropertyKey.INBOUND_BOTTOM,
    WindowCoveringPropertyKey.INBOUND_BOTTOM_NO_POSITION,
    WindowCoveringPropertyKey.INBOUND_LEFT,
    WindowCoveringPropertyKey.INBOUND_LEFT_NO_POSITION,
    WindowCoveringPropertyKey.INBOUND_LEFT_RIGHT,
    WindowCoveringPropertyKey.INBOUND_LEFT_RIGHT_NO_POSITION,
    WindowCoveringPropertyKey.INBOUND_RIGHT,
    WindowCoveringPropertyKey.INBOUND_RIGHT_NO_POSITION,
    WindowCoveringPropertyKey.INBOUND_TOP,
    WindowCoveringPropertyKey.INBOUND_TOP_NO_POSITION,
    WindowCoveringPropertyKey.INBOUND_TOP_BOTTOM,
    WindowCoveringPropertyKey.INBOUND_TOP_BOTTOM_NO_POSITION,
    WindowCoveringPropertyKey.OUTBOUND_BOTTOM,
    WindowCoveringPropertyKey.OUTBOUND_BOTTOM_NO_POSITION,
    WindowCoveringPropertyKey.OUTBOUND_LEFT,
    WindowCoveringPropertyKey.OUTBOUND_LEFT_NO_POSITION,
    WindowCoveringPropertyKey.OUTBOUND_RIGHT,
    WindowCoveringPropertyKey.OUTBOUND_RIGHT_NO_POSITION,
    WindowCoveringPropertyKey.OUTBOUND_TOP,
    WindowCoveringPropertyKey.OUTBOUND_TOP_NO_POSITION,
}

COVER_TILT_PROPERTY_KEYS: set[str | int | None] = {
    WindowCoveringPropertyKey.HORIZONTAL_SLATS_ANGLE,
    WindowCoveringPropertyKey.HORIZONTAL_SLATS_ANGLE_NO_POSITION,
    WindowCoveringPropertyKey.VERTICAL_SLATS_ANGLE,
    WindowCoveringPropertyKey.VERTICAL_SLATS_ANGLE_NO_POSITION,
}

# notification
NOTIFICATION_ACCESS_CONTROL_PROPERTY = "Access Control"
OPENING_STATE_PROPERTY_KEY = "Opening state"


class ZWaveJSService(StrEnum):
    """Store keys for Z-Wave services."""

    CLEAR_LOCK_USERCODE = "clear_lock_usercode"
    GET_LOCK_USERCODE = "get_lock_usercode"
    SET_LOCK_USERCODE = "set_lock_usercode"
    SET_LOCK_CONFIGURATION = "set_lock_configuration"
    SET_USER = "set_user"
    DELETE_USER = "delete_user"
    DELETE_ALL_USERS = "delete_all_users"
    GET_CREDENTIAL_CAPABILITIES = "get_credential_capabilities"
    GET_USERS = "get_users"
    SET_CREDENTIAL = "set_credential"
    DELETE_CREDENTIAL = "delete_credential"
    DELETE_ALL_CREDENTIALS = "delete_all_credentials"
    SET_CONFIG_PARAMETER = "set_config_parameter"
    BULK_SET_PARTIAL_CONFIG_PARAMETERS = "bulk_set_partial_config_parameters"
    REFRESH_VALUE = "refresh_value"
    SET_VALUE = "set_value"
    MULTICAST_SET_VALUE = "multicast_set_value"
    PING = "ping"
    RESET_METER = "reset_meter"
    INVOKE_CC_API = "invoke_cc_api"
    REFRESH_NOTIFICATIONS = "refresh_notifications"


class ZWaveJSServiceArgument(StrEnum):
    """Store keys for Z-Wave service arguments."""

    CODE_SLOT = "code_slot"
    USERCODE = "usercode"
    OPERATION_TYPE = "operation_type"
    LOCK_TIMEOUT = "lock_timeout"
    AUTO_RELOCK_TIME = "auto_relock_time"
    HOLD_AND_RELEASE_TIME = "hold_and_release_time"
    TWIST_ASSIST = "twist_assist"
    BLOCK_TO_BLOCK = "block_to_block"
    USER_ID = "user_id"
    USER_NAME = "user_name"
    USER_TYPE = "user_type"
    CREDENTIAL_RULE = "credential_rule"
    ACTIVE = "active"
    CREDENTIAL_TYPE = "credential_type"
    CREDENTIAL_SLOT = "credential_slot"
    CREDENTIAL_DATA = "credential_data"
    ENDPOINT = "endpoint"
    PARAMETER = "parameter"
    BITMASK = "bitmask"
    VALUE = "value"
    VALUE_SIZE = "value_size"
    VALUE_FORMAT = "value_format"
    REFRESH_ALL_VALUES = "refresh_all_values"
    COMMAND_CLASS = "command_class"
    PROPERTY = "property"
    PROPERTY_KEY = "property_key"
    OPTIONS = "options"
    WAIT_FOR_RESULT = "wait_for_result"
    BROADCAST = "broadcast"
    METER_TYPE = "meter_type"
    METHOD_NAME = "method_name"
    PARAMETERS = "parameters"
    NOTIFICATION_TYPE = "notification_type"
    NOTIFICATION_EVENT = "notification_event"
