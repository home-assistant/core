"""Constants used by multiple MQTT modules."""

import logging

import jinja2

from homeassistant.const import CONF_DISCOVERY, CONF_PAYLOAD, Platform
from homeassistant.exceptions import TemplateError

ATTR_DISCOVERY_HASH = "discovery_hash"
ATTR_DISCOVERY_PAYLOAD = "discovery_payload"
ATTR_DISCOVERY_TOPIC = "discovery_topic"
ATTR_PAYLOAD = "payload"
ATTR_QOS = "qos"
ATTR_RETAIN = "retain"
ATTR_SERIAL_NUMBER = "serial_number"
ATTR_TOPIC = "topic"

AVAILABILITY_ALL = "all"
AVAILABILITY_ANY = "any"
AVAILABILITY_LATEST = "latest"

AVAILABILITY_MODES = [AVAILABILITY_ALL, AVAILABILITY_ANY, AVAILABILITY_LATEST]

CONF_PAYLOAD_AVAILABLE = "payload_available"
CONF_PAYLOAD_NOT_AVAILABLE = "payload_not_available"

CONF_AVAILABILITY = "availability"

CONF_AVAILABILITY_MODE = "availability_mode"
CONF_AVAILABILITY_TEMPLATE = "availability_template"
CONF_AVAILABILITY_TOPIC = "availability_topic"
CONF_BROKER = "broker"
CONF_BIRTH_MESSAGE = "birth_message"
CONF_COMMAND_TEMPLATE = "command_template"
CONF_COMMAND_TOPIC = "command_topic"
CONF_DISCOVERY_PREFIX = "discovery_prefix"
CONF_ENCODING = "encoding"
CONF_JSON_ATTRS_TOPIC = "json_attributes_topic"
CONF_JSON_ATTRS_TEMPLATE = "json_attributes_template"
CONF_KEEPALIVE = "keepalive"
CONF_OPTIONS = "options"
CONF_ORIGIN = "origin"
CONF_QOS = ATTR_QOS
CONF_RETAIN = ATTR_RETAIN
CONF_SCHEMA = "schema"
CONF_STATE_TOPIC = "state_topic"
CONF_STATE_VALUE_TEMPLATE = "state_value_template"
CONF_TOPIC = "topic"
CONF_TRANSPORT = "transport"
CONF_WS_PATH = "ws_path"
CONF_WS_HEADERS = "ws_headers"
CONF_WILL_MESSAGE = "will_message"
CONF_PAYLOAD_RESET = "payload_reset"
CONF_SUPPORTED_FEATURES = "supported_features"

CONF_ACTION_TEMPLATE = "action_template"
CONF_ACTION_TOPIC = "action_topic"
CONF_BLUE_TEMPLATE = "blue_template"
CONF_BRIGHTNESS_COMMAND_TEMPLATE = "brightness_command_template"
CONF_BRIGHTNESS_COMMAND_TOPIC = "brightness_command_topic"
CONF_BRIGHTNESS_SCALE = "brightness_scale"
CONF_BRIGHTNESS_STATE_TOPIC = "brightness_state_topic"
CONF_BRIGHTNESS_TEMPLATE = "brightness_template"
CONF_BRIGHTNESS_VALUE_TEMPLATE = "brightness_value_template"
CONF_COLOR_MODE = "color_mode"
CONF_COLOR_MODE_STATE_TOPIC = "color_mode_state_topic"
CONF_COLOR_MODE_VALUE_TEMPLATE = "color_mode_value_template"
CONF_COLOR_TEMP_COMMAND_TEMPLATE = "color_temp_command_template"
CONF_COLOR_TEMP_COMMAND_TOPIC = "color_temp_command_topic"
CONF_COLOR_TEMP_KELVIN = "color_temp_kelvin"
CONF_COLOR_TEMP_TEMPLATE = "color_temp_template"
CONF_COLOR_TEMP_STATE_TOPIC = "color_temp_state_topic"
CONF_COLOR_TEMP_VALUE_TEMPLATE = "color_temp_value_template"
CONF_COMMAND_OFF_TEMPLATE = "command_off_template"
CONF_COMMAND_ON_TEMPLATE = "command_on_template"
CONF_CURRENT_HUMIDITY_TEMPLATE = "current_humidity_template"
CONF_CURRENT_HUMIDITY_TOPIC = "current_humidity_topic"
CONF_CURRENT_TEMP_TEMPLATE = "current_temperature_template"
CONF_CURRENT_TEMP_TOPIC = "current_temperature_topic"
CONF_DIRECTION_COMMAND_TEMPLATE = "direction_command_template"
CONF_DIRECTION_COMMAND_TOPIC = "direction_command_topic"
CONF_DIRECTION_STATE_TOPIC = "direction_state_topic"
CONF_DIRECTION_VALUE_TEMPLATE = "direction_value_template"
CONF_ENABLED_BY_DEFAULT = "enabled_by_default"
CONF_EFFECT_COMMAND_TEMPLATE = "effect_command_template"
CONF_EFFECT_COMMAND_TOPIC = "effect_command_topic"
CONF_EFFECT_LIST = "effect_list"
CONF_EFFECT_STATE_TOPIC = "effect_state_topic"
CONF_EFFECT_TEMPLATE = "effect_template"
CONF_EFFECT_VALUE_TEMPLATE = "effect_value_template"
CONF_ENTITY_PICTURE = "entity_picture"
CONF_EXPIRE_AFTER = "expire_after"
CONF_FLASH = "flash"
CONF_FLASH_TIME_LONG = "flash_time_long"
CONF_FLASH_TIME_SHORT = "flash_time_short"
CONF_GET_POSITION_TEMPLATE = "position_template"
CONF_GET_POSITION_TOPIC = "position_topic"
CONF_GREEN_TEMPLATE = "green_template"
CONF_HS_COMMAND_TEMPLATE = "hs_command_template"
CONF_HS_COMMAND_TOPIC = "hs_command_topic"
CONF_HS_STATE_TOPIC = "hs_state_topic"
CONF_HS_VALUE_TEMPLATE = "hs_value_template"
CONF_LAST_RESET_VALUE_TEMPLATE = "last_reset_value_template"
CONF_MAX_KELVIN = "max_kelvin"
CONF_MAX_MIREDS = "max_mireds"
CONF_MIN_KELVIN = "min_kelvin"
CONF_MIN_MIREDS = "min_mireds"
CONF_MODE_COMMAND_TEMPLATE = "mode_command_template"
CONF_MODE_COMMAND_TOPIC = "mode_command_topic"
CONF_MODE_LIST = "modes"
CONF_MODE_STATE_TEMPLATE = "mode_state_template"
CONF_MODE_STATE_TOPIC = "mode_state_topic"
CONF_OFF_DELAY = "off_delay"
CONF_ON_COMMAND_TYPE = "on_command_type"
CONF_OSCILLATION_COMMAND_TOPIC = "oscillation_command_topic"
CONF_OSCILLATION_COMMAND_TEMPLATE = "oscillation_command_template"
CONF_OSCILLATION_STATE_TOPIC = "oscillation_state_topic"
CONF_OSCILLATION_VALUE_TEMPLATE = "oscillation_value_template"
CONF_PAYLOAD_CLOSE = "payload_close"
CONF_PAYLOAD_OPEN = "payload_open"
CONF_PAYLOAD_OSCILLATION_OFF = "payload_oscillation_off"
CONF_PAYLOAD_OSCILLATION_ON = "payload_oscillation_on"
CONF_PAYLOAD_PRESS = "payload_press"
CONF_PAYLOAD_RESET_PERCENTAGE = "payload_reset_percentage"
CONF_PAYLOAD_RESET_PRESET_MODE = "payload_reset_preset_mode"
CONF_PAYLOAD_STOP = "payload_stop"
CONF_PAYLOAD_STOP_TILT = "payload_stop_tilt"
CONF_PERCENTAGE_COMMAND_TEMPLATE = "percentage_command_template"
CONF_PERCENTAGE_COMMAND_TOPIC = "percentage_command_topic"
CONF_PERCENTAGE_STATE_TOPIC = "percentage_state_topic"
CONF_PERCENTAGE_VALUE_TEMPLATE = "percentage_value_template"
CONF_POSITION_CLOSED = "position_closed"
CONF_POSITION_OPEN = "position_open"
CONF_POWER_COMMAND_TOPIC = "power_command_topic"
CONF_POWER_COMMAND_TEMPLATE = "power_command_template"
CONF_PRECISION = "precision"
CONF_PRESET_MODE_COMMAND_TEMPLATE = "preset_mode_command_template"
CONF_PRESET_MODE_COMMAND_TOPIC = "preset_mode_command_topic"
CONF_PRESET_MODES_LIST = "preset_modes"
CONF_PRESET_MODE_STATE_TOPIC = "preset_mode_state_topic"
CONF_PRESET_MODE_VALUE_TEMPLATE = "preset_mode_value_template"
CONF_RED_TEMPLATE = "red_template"
CONF_RGB_COMMAND_TEMPLATE = "rgb_command_template"
CONF_RGB_COMMAND_TOPIC = "rgb_command_topic"
CONF_RGB_STATE_TOPIC = "rgb_state_topic"
CONF_RGB_VALUE_TEMPLATE = "rgb_value_template"
CONF_RGBW_COMMAND_TEMPLATE = "rgbw_command_template"
CONF_RGBW_COMMAND_TOPIC = "rgbw_command_topic"
CONF_RGBW_STATE_TOPIC = "rgbw_state_topic"
CONF_RGBW_VALUE_TEMPLATE = "rgbw_value_template"
CONF_RGBWW_COMMAND_TEMPLATE = "rgbww_command_template"
CONF_RGBWW_COMMAND_TOPIC = "rgbww_command_topic"
CONF_RGBWW_STATE_TOPIC = "rgbww_state_topic"
CONF_RGBWW_VALUE_TEMPLATE = "rgbww_value_template"
CONF_SET_POSITION_TEMPLATE = "set_position_template"
CONF_SET_POSITION_TOPIC = "set_position_topic"
CONF_SPEED_RANGE_MAX = "speed_range_max"
CONF_SPEED_RANGE_MIN = "speed_range_min"
CONF_STATE_CLOSED = "state_closed"
CONF_STATE_CLOSING = "state_closing"
CONF_STATE_OFF = "state_off"
CONF_STATE_ON = "state_on"
CONF_STATE_OPEN = "state_open"
CONF_STATE_OPENING = "state_opening"
CONF_STATE_STOPPED = "state_stopped"
CONF_SUGGESTED_DISPLAY_PRECISION = "suggested_display_precision"
CONF_SUPPORTED_COLOR_MODES = "supported_color_modes"
CONF_TEMP_COMMAND_TEMPLATE = "temperature_command_template"
CONF_TEMP_COMMAND_TOPIC = "temperature_command_topic"
CONF_TEMP_STATE_TEMPLATE = "temperature_state_template"
CONF_TEMP_STATE_TOPIC = "temperature_state_topic"
CONF_TEMP_INITIAL = "initial"
CONF_TEMP_MAX = "max_temp"
CONF_TEMP_MIN = "min_temp"
CONF_TILT_COMMAND_TEMPLATE = "tilt_command_template"
CONF_TILT_COMMAND_TOPIC = "tilt_command_topic"
CONF_TILT_STATUS_TOPIC = "tilt_status_topic"
CONF_TILT_STATUS_TEMPLATE = "tilt_status_template"
CONF_TILT_CLOSED_POSITION = "tilt_closed_value"
CONF_TILT_MAX = "tilt_max"
CONF_TILT_MIN = "tilt_min"
CONF_TILT_OPEN_POSITION = "tilt_opened_value"
CONF_TILT_STATE_OPTIMISTIC = "tilt_optimistic"
CONF_TRANSITION = "transition"
CONF_XY_COMMAND_TEMPLATE = "xy_command_template"
CONF_XY_COMMAND_TOPIC = "xy_command_topic"
CONF_XY_STATE_TOPIC = "xy_state_topic"
CONF_XY_VALUE_TEMPLATE = "xy_value_template"
CONF_WHITE_COMMAND_TOPIC = "white_command_topic"
CONF_WHITE_SCALE = "white_scale"

# Config flow constants
CONF_CERTIFICATE = "certificate"
CONF_CLIENT_KEY = "client_key"
CONF_CLIENT_CERT = "client_cert"
CONF_COMPONENTS = "components"
CONF_TLS_INSECURE = "tls_insecure"

# Device and integration info options
CONF_IDENTIFIERS = "identifiers"
CONF_CONNECTIONS = "connections"
CONF_MANUFACTURER = "manufacturer"
CONF_HW_VERSION = "hw_version"
CONF_SW_VERSION = "sw_version"
CONF_SERIAL_NUMBER = "serial_number"
CONF_VIA_DEVICE = "via_device"
CONF_DEPRECATED_VIA_HUB = "via_hub"
CONF_SUGGESTED_AREA = "suggested_area"
CONF_CONFIGURATION_URL = "configuration_url"
CONF_OBJECT_ID = "object_id"
CONF_SUPPORT_URL = "support_url"

DEFAULT_BRIGHTNESS = False
DEFAULT_BRIGHTNESS_SCALE = 255
DEFAULT_PREFIX = "homeassistant"
DEFAULT_BIRTH_WILL_TOPIC = DEFAULT_PREFIX + "/status"
DEFAULT_DISCOVERY = True
DEFAULT_EFFECT = False
DEFAULT_ENCODING = "utf-8"
DEFAULT_FLASH_TIME_LONG = 10
DEFAULT_FLASH_TIME_SHORT = 2
DEFAULT_OPTIMISTIC = False
DEFAULT_ON_COMMAND_TYPE = "last"
DEFAULT_QOS = 0
DEFAULT_PAYLOAD_AVAILABLE = "online"
DEFAULT_PAYLOAD_CLOSE = "CLOSE"
DEFAULT_PAYLOAD_NOT_AVAILABLE = "offline"
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OPEN = "OPEN"
DEFAULT_PAYLOAD_OSCILLATE_OFF = "oscillate_off"
DEFAULT_PAYLOAD_OSCILLATE_ON = "oscillate_on"
DEFAULT_PAYLOAD_PRESS = "PRESS"
DEFAULT_PAYLOAD_STOP = "STOP"
DEFAULT_PAYLOAD_RESET = "None"
DEFAULT_PORT = 1883
DEFAULT_RETAIN = False
DEFAULT_TILT_CLOSED_POSITION = 0
DEFAULT_TILT_MAX = 100
DEFAULT_TILT_MIN = 0
DEFAULT_TILT_OPEN_POSITION = 100
DEFAULT_TILT_OPTIMISTIC = False
DEFAULT_WS_HEADERS: dict[str, str] = {}
DEFAULT_WS_PATH = "/"
DEFAULT_POSITION_CLOSED = 0
DEFAULT_POSITION_OPEN = 100
DEFAULT_RETAIN = False
DEFAULT_SPEED_RANGE_MAX = 100
DEFAULT_SPEED_RANGE_MIN = 1
DEFAULT_STATE_STOPPED = "stopped"
DEFAULT_WHITE_SCALE = 255

COVER_PAYLOAD = "cover"
TILT_PAYLOAD = "tilt"

VALUES_ON_COMMAND_TYPE = ["first", "last", "brightness"]

PROTOCOL_31 = "3.1"
PROTOCOL_311 = "3.1.1"
PROTOCOL_5 = "5"
SUPPORTED_PROTOCOLS = [PROTOCOL_31, PROTOCOL_311, PROTOCOL_5]

TRANSPORT_TCP = "tcp"
TRANSPORT_WEBSOCKETS = "websockets"

DEFAULT_PORT = 1883
DEFAULT_KEEPALIVE = 60
DEFAULT_PROTOCOL = PROTOCOL_311
DEFAULT_TRANSPORT = TRANSPORT_TCP

DEFAULT_BIRTH = {
    ATTR_TOPIC: DEFAULT_BIRTH_WILL_TOPIC,
    CONF_PAYLOAD: DEFAULT_PAYLOAD_AVAILABLE,
    ATTR_QOS: DEFAULT_QOS,
    ATTR_RETAIN: DEFAULT_RETAIN,
}

DEFAULT_WILL = {
    ATTR_TOPIC: DEFAULT_BIRTH_WILL_TOPIC,
    CONF_PAYLOAD: DEFAULT_PAYLOAD_NOT_AVAILABLE,
    ATTR_QOS: DEFAULT_QOS,
    ATTR_RETAIN: DEFAULT_RETAIN,
}

DOMAIN = "mqtt"
LOGGER = logging.getLogger(__package__)

MQTT_CONNECTION_STATE = "mqtt_connection_state"

PAYLOAD_EMPTY_JSON = "{}"
PAYLOAD_NONE = "None"

CONFIG_ENTRY_VERSION = 1
CONFIG_ENTRY_MINOR_VERSION = 2

# Split mqtt entry data and options
# Can be removed when config entry is bumped to version 2.1
# with HA Core 2026.1.0. Read support for version 2.1 is expected before 2026.1
# From 2026.1 we will write version 2.1
ENTRY_OPTION_FIELDS = (
    CONF_DISCOVERY,
    CONF_DISCOVERY_PREFIX,
    "birth_message",
    "will_message",
)

ENTITY_PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.DEVICE_TRACKER,
    Platform.EVENT,
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.LAWN_MOWER,
    Platform.LOCK,
    Platform.NOTIFY,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.UPDATE,
    Platform.VACUUM,
    Platform.VALVE,
    Platform.WATER_HEATER,
]

TEMPLATE_ERRORS = (jinja2.TemplateError, TemplateError, TypeError, ValueError)

SUPPORTED_COMPONENTS = (
    "alarm_control_panel",
    "binary_sensor",
    "button",
    "camera",
    "climate",
    "cover",
    "device_automation",
    "device_tracker",
    "event",
    "fan",
    "humidifier",
    "image",
    "lawn_mower",
    "light",
    "lock",
    "notify",
    "number",
    "scene",
    "siren",
    "select",
    "sensor",
    "switch",
    "tag",
    "text",
    "update",
    "vacuum",
    "valve",
    "water_heater",
)
