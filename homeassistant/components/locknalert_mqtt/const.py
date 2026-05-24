"""Constants used by multiple MQTT modules."""

import logging

import jinja2

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.const import CONF_DISCOVERY, CONF_PAYLOAD, Platform
from homeassistant.exceptions import TemplateError

ATTR_DISCOVERY_HASH = "discovery_hash"
ATTR_DISCOVERY_PAYLOAD = "discovery_payload"
ATTR_DISCOVERY_TOPIC = "discovery_topic"
ATTR_PAYLOAD = "payload"
ATTR_QOS = "qos"
ATTR_RETAIN = "retain"
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
CONF_CODE_ARM_REQUIRED = "code_arm_required"
CONF_CODE_DISARM_REQUIRED = "code_disarm_required"
CONF_CODE_FORMAT = "code_format"
CONF_CODE_TRIGGER_REQUIRED = "code_trigger_required"
CONF_COMMAND_TEMPLATE = "command_template"
CONF_COMMAND_TOPIC = "command_topic"
CONF_DEFAULT_ENTITY_ID = "default_entity_id"
CONF_DISCOVERY_PREFIX = "discovery_prefix"
CONF_ENCODING = "encoding"
CONF_JSON_ATTRS_TOPIC = "json_attributes_topic"
CONF_JSON_ATTRS_TEMPLATE = "json_attributes_template"
CONF_KEEPALIVE = "keepalive"
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
CONF_SUPPORTED_FEATURES = "supported_features"
CONF_ENABLED_BY_DEFAULT = "enabled_by_default"
CONF_ENTITY_PICTURE = "entity_picture"
CONF_GROUP = "group"
CONF_MAX = "max"
CONF_MIN = "min"
CONF_PAYLOAD_ARM_AWAY = "payload_arm_away"
CONF_PAYLOAD_ARM_CUSTOM_BYPASS = "payload_arm_custom_bypass"
CONF_PAYLOAD_ARM_HOME = "payload_arm_home"
CONF_PAYLOAD_ARM_NIGHT = "payload_arm_night"
CONF_PAYLOAD_ARM_VACATION = "payload_arm_vacation"
CONF_PAYLOAD_DISARM = "payload_disarm"
CONF_PAYLOAD_TRIGGER = "payload_trigger"

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
CONF_SUPPORT_URL = "support_url"

DEFAULT_ALARM_CONTROL_PANEL_COMMAND_TEMPLATE = "{{action}}"
DEFAULT_API_PORT = 443
DEFAULT_PREFIX = "homeassistant"
DEFAULT_BIRTH_WILL_TOPIC = DEFAULT_PREFIX + "/status"
DEFAULT_DISCOVERY = True
DEFAULT_ENCODING = "utf-8"
DEFAULT_OPTIMISTIC = False
DEFAULT_QOS = 0

DEFAULT_PAYLOAD_ARM_AWAY = "ARM_AWAY"
DEFAULT_PAYLOAD_ARM_CUSTOM_BYPASS = "ARM_CUSTOM_BYPASS"
DEFAULT_PAYLOAD_ARM_HOME = "ARM_HOME"
DEFAULT_PAYLOAD_ARM_NIGHT = "ARM_NIGHT"
DEFAULT_PAYLOAD_ARM_VACATION = "ARM_VACATION"
DEFAULT_PAYLOAD_AVAILABLE = "online"
DEFAULT_PAYLOAD_DISARM = "DISARM"
DEFAULT_PAYLOAD_NOT_AVAILABLE = "offline"
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_TRIGGER = "TRIGGER"
DEFAULT_RETAIN = False
DEFAULT_WS_HEADERS: dict[str, str] = {}
DEFAULT_WS_PATH = "/"

ALARM_CONTROL_PANEL_SUPPORTED_FEATURES = {
    "arm_home": AlarmControlPanelEntityFeature.ARM_HOME,
    "arm_away": AlarmControlPanelEntityFeature.ARM_AWAY,
    "arm_night": AlarmControlPanelEntityFeature.ARM_NIGHT,
    "arm_vacation": AlarmControlPanelEntityFeature.ARM_VACATION,
    "arm_custom_bypass": AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS,
    "trigger": AlarmControlPanelEntityFeature.TRIGGER,
}
REMOTE_CODE = "REMOTE_CODE"
REMOTE_CODE_TEXT = "REMOTE_CODE_TEXT"

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

DOMAIN = "locknalert_mqtt"
LOGGER = logging.getLogger(__package__)

MQTT_CONNECTION_STATE = "mqtt_connection_state"
MQTT_PROCESSED_SUBSCRIPTIONS = "mqtt_processed_subscriptions"

PAYLOAD_EMPTY_JSON = "{}"
PAYLOAD_NONE = "None"

# LocknAlert Bridge API Discovery
CONF_BRIDGE_SERIAL = "bridge_serial"

# Discovery attribute names from zeroconf TXT properties
DISCOVERY_ATTR_API_PORT = "api_port"
DISCOVERY_ATTR_SERIAL = "bridge_serial"

CONFIG_ENTRY_VERSION = 2
CONFIG_ENTRY_MINOR_VERSION = 1

# Split mqtt entry data and options
# Can be removed when config entry is bumped to version 2.1
# with HA Core 2026.7.0. Read support for version 2.1 is expected from 2026.1
# From 2026.7 we will write version 2.1
ENTRY_OPTION_FIELDS = (
    CONF_DISCOVERY,
    CONF_DISCOVERY_PREFIX,
    "birth_message",
    "will_message",
)

ENTITY_PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
]

TEMPLATE_ERRORS = (jinja2.TemplateError, TemplateError, TypeError, ValueError)

SUPPORTED_COMPONENTS = ("alarm_control_panel",)
