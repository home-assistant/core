"""Constants used by multiple MQTT modules."""

from enum import IntFlag
import logging

import jinja2

from homeassistant.const import CONF_PAYLOAD, Platform
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
CONF_CURRENT_HUMIDITY_TEMPLATE = "current_humidity_template"
CONF_CURRENT_HUMIDITY_TOPIC = "current_humidity_topic"
CONF_CURRENT_TEMP_TEMPLATE = "current_temperature_template"
CONF_CURRENT_TEMP_TOPIC = "current_temperature_topic"
CONF_ENABLED_BY_DEFAULT = "enabled_by_default"
CONF_MODE_COMMAND_TEMPLATE = "mode_command_template"
CONF_MODE_COMMAND_TOPIC = "mode_command_topic"
CONF_MODE_LIST = "modes"
CONF_MODE_STATE_TEMPLATE = "mode_state_template"
CONF_MODE_STATE_TOPIC = "mode_state_topic"
CONF_PAYLOAD_CLOSE = "payload_close"
CONF_PAYLOAD_OPEN = "payload_open"
CONF_PAYLOAD_STOP = "payload_stop"
CONF_POSITION_CLOSED = "position_closed"
CONF_POSITION_OPEN = "position_open"
CONF_POWER_COMMAND_TOPIC = "power_command_topic"
CONF_POWER_COMMAND_TEMPLATE = "power_command_template"
CONF_PRECISION = "precision"
CONF_STATE_CLOSED = "state_closed"
CONF_STATE_CLOSING = "state_closing"
CONF_STATE_OPEN = "state_open"
CONF_STATE_OPENING = "state_opening"
CONF_TEMP_COMMAND_TEMPLATE = "temperature_command_template"
CONF_TEMP_COMMAND_TOPIC = "temperature_command_topic"
CONF_TEMP_STATE_TEMPLATE = "temperature_state_template"
CONF_TEMP_STATE_TOPIC = "temperature_state_topic"
CONF_TEMP_INITIAL = "initial"
CONF_TEMP_MAX = "max_temp"
CONF_TEMP_MIN = "min_temp"

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

CONF_MIGRATE_DISCOVERY = "migrate_discovery"

DEFAULT_PREFIX = "homeassistant"
DEFAULT_BIRTH_WILL_TOPIC = DEFAULT_PREFIX + "/status"
DEFAULT_DISCOVERY = True
DEFAULT_ENCODING = "utf-8"
DEFAULT_OPTIMISTIC = False
DEFAULT_QOS = 0
DEFAULT_PAYLOAD_AVAILABLE = "online"
DEFAULT_PAYLOAD_CLOSE = "CLOSE"
DEFAULT_PAYLOAD_NOT_AVAILABLE = "offline"
DEFAULT_PAYLOAD_OPEN = "OPEN"
DEFAULT_PORT = 1883
DEFAULT_RETAIN = False
DEFAULT_WS_HEADERS: dict[str, str] = {}
DEFAULT_WS_PATH = "/"
DEFAULT_POSITION_CLOSED = 0
DEFAULT_POSITION_OPEN = 100
DEFAULT_RETAIN = False

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

RELOADABLE_PLATFORMS = [
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


class MqttDiscoveryType(IntFlag):
    """Flag to indicate the discovery type supported."""

    SINGLE_COMPONENT = 1
    DEVICE = 2


SUPPORTED_COMPONENTS = {
    "alarm_control_panel": MqttDiscoveryType.SINGLE_COMPONENT,
    "binary_sensor": MqttDiscoveryType.SINGLE_COMPONENT,
    "button": MqttDiscoveryType.SINGLE_COMPONENT,
    "camera": MqttDiscoveryType.SINGLE_COMPONENT,
    "climate": MqttDiscoveryType.SINGLE_COMPONENT,
    "cover": MqttDiscoveryType.SINGLE_COMPONENT,
    "device": MqttDiscoveryType.DEVICE,
    "device_automation": MqttDiscoveryType.SINGLE_COMPONENT,
    "device_tracker": MqttDiscoveryType.SINGLE_COMPONENT,
    "event": MqttDiscoveryType.SINGLE_COMPONENT,
    "fan": MqttDiscoveryType.SINGLE_COMPONENT,
    "humidifier": MqttDiscoveryType.SINGLE_COMPONENT,
    "image": MqttDiscoveryType.SINGLE_COMPONENT,
    "lawn_mower": MqttDiscoveryType.SINGLE_COMPONENT,
    "light": MqttDiscoveryType.SINGLE_COMPONENT,
    "lock": MqttDiscoveryType.SINGLE_COMPONENT,
    "notify": MqttDiscoveryType.SINGLE_COMPONENT,
    "number": MqttDiscoveryType.SINGLE_COMPONENT,
    "scene": MqttDiscoveryType.SINGLE_COMPONENT,
    "siren": MqttDiscoveryType.SINGLE_COMPONENT,
    "select": MqttDiscoveryType.SINGLE_COMPONENT,
    "sensor": MqttDiscoveryType.SINGLE_COMPONENT,
    "switch": MqttDiscoveryType.SINGLE_COMPONENT,
    "tag": MqttDiscoveryType.SINGLE_COMPONENT,
    "text": MqttDiscoveryType.SINGLE_COMPONENT,
    "update": MqttDiscoveryType.SINGLE_COMPONENT,
    "vacuum": MqttDiscoveryType.SINGLE_COMPONENT,
    "valve": MqttDiscoveryType.SINGLE_COMPONENT,
    "water_heater": MqttDiscoveryType.SINGLE_COMPONENT,
}
