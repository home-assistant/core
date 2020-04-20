"""All constants related to the ZHA component."""
import enum
import logging

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.cover import DOMAIN as COVER
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER
from homeassistant.components.fan import DOMAIN as FAN
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.lock import DOMAIN as LOCK
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH

ATTR_ARGS = "args"
ATTR_ATTRIBUTE = "attribute"
ATTR_ATTRIBUTE_ID = "attribute_id"
ATTR_ATTRIBUTE_NAME = "attribute_name"
ATTR_AVAILABLE = "available"
ATTR_CLUSTER_ID = "cluster_id"
ATTR_CLUSTER_TYPE = "cluster_type"
ATTR_COMMAND = "command"
ATTR_COMMAND_TYPE = "command_type"
ATTR_DEVICE_IEEE = "device_ieee"
ATTR_DEVICE_TYPE = "device_type"
ATTR_ENDPOINTS = "endpoints"
ATTR_ENDPOINT_ID = "endpoint_id"
ATTR_IEEE = "ieee"
ATTR_IN_CLUSTERS = "in_clusters"
ATTR_LAST_SEEN = "last_seen"
ATTR_LEVEL = "level"
ATTR_LQI = "lqi"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MANUFACTURER_CODE = "manufacturer_code"
ATTR_MEMBERS = "members"
ATTR_MODEL = "model"
ATTR_NAME = "name"
ATTR_NODE_DESCRIPTOR = "node_descriptor"
ATTR_NWK = "nwk"
ATTR_OUT_CLUSTERS = "out_clusters"
ATTR_POWER_SOURCE = "power_source"
ATTR_PROFILE_ID = "profile_id"
ATTR_QUIRK_APPLIED = "quirk_applied"
ATTR_QUIRK_CLASS = "quirk_class"
ATTR_RSSI = "rssi"
ATTR_SIGNATURE = "signature"
ATTR_TYPE = "type"
ATTR_UNIQUE_ID = "unique_id"
ATTR_VALUE = "value"
ATTR_WARNING_DEVICE_DURATION = "duration"
ATTR_WARNING_DEVICE_MODE = "mode"
ATTR_WARNING_DEVICE_STROBE = "strobe"
ATTR_WARNING_DEVICE_STROBE_DUTY_CYCLE = "duty_cycle"
ATTR_WARNING_DEVICE_STROBE_INTENSITY = "intensity"

BAUD_RATES = [2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 128000, 256000]
BINDINGS = "bindings"

CHANNEL_ACCELEROMETER = "accelerometer"
CHANNEL_ANALOG_INPUT = "analog_input"
CHANNEL_ATTRIBUTE = "attribute"
CHANNEL_BASIC = "basic"
CHANNEL_COLOR = "light_color"
CHANNEL_COVER = "window_covering"
CHANNEL_DOORLOCK = "door_lock"
CHANNEL_ELECTRICAL_MEASUREMENT = "electrical_measurement"
CHANNEL_EVENT_RELAY = "event_relay"
CHANNEL_FAN = "fan"
CHANNEL_HUMIDITY = "humidity"
CHANNEL_IAS_WD = "ias_wd"
CHANNEL_IDENTIFY = "identify"
CHANNEL_ILLUMINANCE = "illuminance"
CHANNEL_LEVEL = ATTR_LEVEL
CHANNEL_MULTISTATE_INPUT = "multistate_input"
CHANNEL_OCCUPANCY = "occupancy"
CHANNEL_ON_OFF = "on_off"
CHANNEL_POWER_CONFIGURATION = "power"
CHANNEL_PRESSURE = "pressure"
CHANNEL_SMARTENERGY_METERING = "smartenergy_metering"
CHANNEL_TEMPERATURE = "temperature"
CHANNEL_ZDO = "zdo"
CHANNEL_ZONE = ZONE = "ias_zone"

CLUSTER_COMMAND_SERVER = "server"
CLUSTER_COMMANDS_CLIENT = "client_commands"
CLUSTER_COMMANDS_SERVER = "server_commands"
CLUSTER_TYPE_IN = "in"
CLUSTER_TYPE_OUT = "out"

COMPONENTS = (BINARY_SENSOR, COVER, DEVICE_TRACKER, FAN, LIGHT, LOCK, SENSOR, SWITCH)

CONF_BAUDRATE = "baudrate"
CONF_DATABASE = "database_path"
CONF_DEVICE_CONFIG = "device_config"
CONF_ENABLE_QUIRKS = "enable_quirks"
CONF_RADIO_TYPE = "radio_type"
CONF_USB_PATH = "usb_path"
CONTROLLER = "controller"

DATA_DEVICE_CONFIG = "zha_device_config"
DATA_ZHA = "zha"
DATA_ZHA_CONFIG = "config"
DATA_ZHA_BRIDGE_ID = "zha_bridge_id"
DATA_ZHA_CORE_EVENTS = "zha_core_events"
DATA_ZHA_DISPATCHERS = "zha_dispatchers"
DATA_ZHA_GATEWAY = "zha_gateway"
DATA_ZHA_PLATFORM_LOADED = "platform_loaded"

DEBUG_COMP_BELLOWS = "bellows"
DEBUG_COMP_ZHA = "homeassistant.components.zha"
DEBUG_COMP_ZIGPY = "zigpy"
DEBUG_COMP_ZIGPY_CC = "zigpy_cc"
DEBUG_COMP_ZIGPY_DECONZ = "zigpy_deconz"
DEBUG_COMP_ZIGPY_XBEE = "zigpy_xbee"
DEBUG_COMP_ZIGPY_ZIGATE = "zigpy_zigate"
DEBUG_LEVEL_CURRENT = "current"
DEBUG_LEVEL_ORIGINAL = "original"
DEBUG_LEVELS = {
    DEBUG_COMP_BELLOWS: logging.DEBUG,
    DEBUG_COMP_ZHA: logging.DEBUG,
    DEBUG_COMP_ZIGPY: logging.DEBUG,
    DEBUG_COMP_ZIGPY_CC: logging.DEBUG,
    DEBUG_COMP_ZIGPY_DECONZ: logging.DEBUG,
    DEBUG_COMP_ZIGPY_XBEE: logging.DEBUG,
    DEBUG_COMP_ZIGPY_ZIGATE: logging.DEBUG,
}
DEBUG_RELAY_LOGGERS = [DEBUG_COMP_ZHA, DEBUG_COMP_ZIGPY]

DEFAULT_RADIO_TYPE = "ezsp"
DEFAULT_BAUDRATE = 57600
DEFAULT_DATABASE_NAME = "zigbee.db"
DISCOVERY_KEY = "zha_discovery_info"

DOMAIN = "zha"

GROUP_ID = "group_id"
GROUP_IDS = "group_ids"
GROUP_NAME = "group_name"

MFG_CLUSTER_ID_START = 0xFC00

POWER_MAINS_POWERED = "Mains"
POWER_BATTERY_OR_UNKNOWN = "Battery or Unknown"


class RadioType(enum.Enum):
    """Possible options for radio type."""

    deconz = "deconz"
    ezsp = "ezsp"
    ti_cc = "ti_cc"
    xbee = "xbee"
    zigate = "zigate"

    @classmethod
    def list(cls):
        """Return list of enum's values."""
        return [e.value for e in RadioType]


REPORT_CONFIG_MAX_INT = 900
REPORT_CONFIG_MAX_INT_BATTERY_SAVE = 10800
REPORT_CONFIG_MIN_INT = 30
REPORT_CONFIG_MIN_INT_ASAP = 1
REPORT_CONFIG_MIN_INT_IMMEDIATE = 0
REPORT_CONFIG_MIN_INT_OP = 5
REPORT_CONFIG_MIN_INT_BATTERY_SAVE = 3600
REPORT_CONFIG_RPT_CHANGE = 1
REPORT_CONFIG_DEFAULT = (
    REPORT_CONFIG_MIN_INT,
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_RPT_CHANGE,
)
REPORT_CONFIG_ASAP = (
    REPORT_CONFIG_MIN_INT_ASAP,
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_RPT_CHANGE,
)
REPORT_CONFIG_BATTERY_SAVE = (
    REPORT_CONFIG_MIN_INT_BATTERY_SAVE,
    REPORT_CONFIG_MAX_INT_BATTERY_SAVE,
    REPORT_CONFIG_RPT_CHANGE,
)
REPORT_CONFIG_IMMEDIATE = (
    REPORT_CONFIG_MIN_INT_IMMEDIATE,
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_RPT_CHANGE,
)
REPORT_CONFIG_OP = (
    REPORT_CONFIG_MIN_INT_OP,
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_RPT_CHANGE,
)

SENSOR_ACCELERATION = "acceleration"
SENSOR_BATTERY = "battery"
SENSOR_ELECTRICAL_MEASUREMENT = CHANNEL_ELECTRICAL_MEASUREMENT
SENSOR_GENERIC = "generic"
SENSOR_HUMIDITY = CHANNEL_HUMIDITY
SENSOR_ILLUMINANCE = CHANNEL_ILLUMINANCE
SENSOR_METERING = "metering"
SENSOR_OCCUPANCY = CHANNEL_OCCUPANCY
SENSOR_OPENING = "opening"
SENSOR_PRESSURE = CHANNEL_PRESSURE
SENSOR_TEMPERATURE = CHANNEL_TEMPERATURE
SENSOR_TYPE = "sensor_type"

SIGNAL_ADD_ENTITIES = "zha_add_new_entities"
SIGNAL_ATTR_UPDATED = "attribute_updated"
SIGNAL_AVAILABLE = "available"
SIGNAL_MOVE_LEVEL = "move_level"
SIGNAL_REMOVE = "remove"
SIGNAL_SET_LEVEL = "set_level"
SIGNAL_STATE_ATTR = "update_state_attribute"
SIGNAL_UPDATE_DEVICE = "{}_zha_update_device"
SIGNAL_REMOVE_GROUP = "remove_group"
SIGNAL_GROUP_ENTITY_REMOVED = "group_entity_removed"
SIGNAL_GROUP_MEMBERSHIP_CHANGE = "group_membership_change"

UNKNOWN = "unknown"
UNKNOWN_MANUFACTURER = "unk_manufacturer"
UNKNOWN_MODEL = "unk_model"

WARNING_DEVICE_MODE_STOP = 0
WARNING_DEVICE_MODE_BURGLAR = 1
WARNING_DEVICE_MODE_FIRE = 2
WARNING_DEVICE_MODE_EMERGENCY = 3
WARNING_DEVICE_MODE_POLICE_PANIC = 4
WARNING_DEVICE_MODE_FIRE_PANIC = 5
WARNING_DEVICE_MODE_EMERGENCY_PANIC = 6

WARNING_DEVICE_STROBE_NO = 0
WARNING_DEVICE_STROBE_YES = 1

WARNING_DEVICE_SOUND_LOW = 0
WARNING_DEVICE_SOUND_MEDIUM = 1
WARNING_DEVICE_SOUND_HIGH = 2
WARNING_DEVICE_SOUND_VERY_HIGH = 3

WARNING_DEVICE_STROBE_LOW = 0x00
WARNING_DEVICE_STROBE_MEDIUM = 0x01
WARNING_DEVICE_STROBE_HIGH = 0x02
WARNING_DEVICE_STROBE_VERY_HIGH = 0x03

WARNING_DEVICE_SQUAWK_MODE_ARMED = 0
WARNING_DEVICE_SQUAWK_MODE_DISARMED = 1

ZHA_DISCOVERY_NEW = "zha_discovery_new_{}"
ZHA_GW_MSG = "zha_gateway_message"
ZHA_GW_MSG_DEVICE_FULL_INIT = "device_fully_initialized"
ZHA_GW_MSG_DEVICE_INFO = "device_info"
ZHA_GW_MSG_DEVICE_JOINED = "device_joined"
ZHA_GW_MSG_DEVICE_REMOVED = "device_removed"
ZHA_GW_MSG_GROUP_ADDED = "group_added"
ZHA_GW_MSG_GROUP_INFO = "group_info"
ZHA_GW_MSG_GROUP_MEMBER_ADDED = "group_member_added"
ZHA_GW_MSG_GROUP_MEMBER_REMOVED = "group_member_removed"
ZHA_GW_MSG_GROUP_REMOVED = "group_removed"
ZHA_GW_MSG_LOG_ENTRY = "log_entry"
ZHA_GW_MSG_LOG_OUTPUT = "log_output"
ZHA_GW_MSG_RAW_INIT = "raw_device_initialized"
ZHA_GW_RADIO = "radio"
ZHA_GW_RADIO_DESCRIPTION = "radio_description"

EFFECT_BLINK = 0x00
EFFECT_BREATHE = 0x01
EFFECT_OKAY = 0x02

EFFECT_DEFAULT_VARIANT = 0x00
