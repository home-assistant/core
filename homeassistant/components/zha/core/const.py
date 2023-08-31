"""All constants related to the ZHA component."""
from __future__ import annotations

import enum
import logging

import bellows.zigbee.application
import voluptuous as vol
import zigpy.application
import zigpy.types as t
import zigpy_deconz.zigbee.application
import zigpy_xbee.zigbee.application
import zigpy_zigate.zigbee.application
import zigpy_znp.zigbee.application

from homeassistant.const import Platform
import homeassistant.helpers.config_validation as cv

ATTR_ACTIVE_COORDINATOR = "active_coordinator"
ATTR_ARGS = "args"
ATTR_ATTRIBUTE = "attribute"
ATTR_ATTRIBUTE_ID = "attribute_id"
ATTR_ATTRIBUTE_NAME = "attribute_name"
ATTR_AVAILABLE = "available"
ATTR_CLUSTER_ID = "cluster_id"
ATTR_CLUSTER_TYPE = "cluster_type"
ATTR_COMMAND_TYPE = "command_type"
ATTR_DEVICE_IEEE = "device_ieee"
ATTR_DEVICE_TYPE = "device_type"
ATTR_ENDPOINTS = "endpoints"
ATTR_ENDPOINT_NAMES = "endpoint_names"
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
ATTR_NEIGHBORS = "neighbors"
ATTR_NODE_DESCRIPTOR = "node_descriptor"
ATTR_NWK = "nwk"
ATTR_OUT_CLUSTERS = "out_clusters"
ATTR_PARAMS = "params"
ATTR_POWER_SOURCE = "power_source"
ATTR_PROFILE_ID = "profile_id"
ATTR_QUIRK_APPLIED = "quirk_applied"
ATTR_QUIRK_CLASS = "quirk_class"
ATTR_ROUTES = "routes"
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

CLUSTER_HANDLER_ACCELEROMETER = "accelerometer"
CLUSTER_HANDLER_BINARY_INPUT = "binary_input"
CLUSTER_HANDLER_ANALOG_INPUT = "analog_input"
CLUSTER_HANDLER_ANALOG_OUTPUT = "analog_output"
CLUSTER_HANDLER_ATTRIBUTE = "attribute"
CLUSTER_HANDLER_BASIC = "basic"
CLUSTER_HANDLER_COLOR = "light_color"
CLUSTER_HANDLER_COVER = "window_covering"
CLUSTER_HANDLER_DEVICE_TEMPERATURE = "device_temperature"
CLUSTER_HANDLER_DOORLOCK = "door_lock"
CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT = "electrical_measurement"
CLUSTER_HANDLER_EVENT_RELAY = "event_relay"
CLUSTER_HANDLER_FAN = "fan"
CLUSTER_HANDLER_HUMIDITY = "humidity"
CLUSTER_HANDLER_HUE_OCCUPANCY = "philips_occupancy"
CLUSTER_HANDLER_SOIL_MOISTURE = "soil_moisture"
CLUSTER_HANDLER_LEAF_WETNESS = "leaf_wetness"
CLUSTER_HANDLER_IAS_ACE = "ias_ace"
CLUSTER_HANDLER_IAS_WD = "ias_wd"
CLUSTER_HANDLER_IDENTIFY = "identify"
CLUSTER_HANDLER_ILLUMINANCE = "illuminance"
CLUSTER_HANDLER_LEVEL = ATTR_LEVEL
CLUSTER_HANDLER_MULTISTATE_INPUT = "multistate_input"
CLUSTER_HANDLER_OCCUPANCY = "occupancy"
CLUSTER_HANDLER_ON_OFF = "on_off"
CLUSTER_HANDLER_POWER_CONFIGURATION = "power"
CLUSTER_HANDLER_PRESSURE = "pressure"
CLUSTER_HANDLER_SHADE = "shade"
CLUSTER_HANDLER_SMARTENERGY_METERING = "smartenergy_metering"
CLUSTER_HANDLER_TEMPERATURE = "temperature"
CLUSTER_HANDLER_THERMOSTAT = "thermostat"
CLUSTER_HANDLER_ZDO = "zdo"
CLUSTER_HANDLER_ZONE = ZONE = "ias_zone"
CLUSTER_HANDLER_INOVELLI = "inovelli_vzm31sn_cluster"

CLUSTER_COMMAND_SERVER = "server"
CLUSTER_COMMANDS_CLIENT = "client_commands"
CLUSTER_COMMANDS_SERVER = "server_commands"
CLUSTER_TYPE_IN = "in"
CLUSTER_TYPE_OUT = "out"

PLATFORMS = (
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.DEVICE_TRACKER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
)

CONF_ALARM_MASTER_CODE = "alarm_master_code"
CONF_ALARM_FAILED_TRIES = "alarm_failed_tries"
CONF_ALARM_ARM_REQUIRES_CODE = "alarm_arm_requires_code"

CONF_BAUDRATE = "baudrate"
CONF_CUSTOM_QUIRKS_PATH = "custom_quirks_path"
CONF_DEFAULT_LIGHT_TRANSITION = "default_light_transition"
CONF_DEVICE_CONFIG = "device_config"
CONF_ENABLE_ENHANCED_LIGHT_TRANSITION = "enhanced_light_transition"
CONF_ENABLE_LIGHT_TRANSITIONING_FLAG = "light_transitioning_flag"
CONF_ALWAYS_PREFER_XY_COLOR_MODE = "always_prefer_xy_color_mode"
CONF_GROUP_MEMBERS_ASSUME_STATE = "group_members_assume_state"
CONF_ENABLE_IDENTIFY_ON_JOIN = "enable_identify_on_join"
CONF_ENABLE_QUIRKS = "enable_quirks"
CONF_FLOWCONTROL = "flow_control"
CONF_RADIO_TYPE = "radio_type"
CONF_USB_PATH = "usb_path"
CONF_USE_THREAD = "use_thread"
CONF_ZIGPY = "zigpy_config"

CONF_CONSIDER_UNAVAILABLE_MAINS = "consider_unavailable_mains"
CONF_DEFAULT_CONSIDER_UNAVAILABLE_MAINS = 60 * 60 * 2  # 2 hours
CONF_CONSIDER_UNAVAILABLE_BATTERY = "consider_unavailable_battery"
CONF_DEFAULT_CONSIDER_UNAVAILABLE_BATTERY = 60 * 60 * 6  # 6 hours

CONF_ZHA_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEFAULT_LIGHT_TRANSITION, default=0): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=2**16 / 10)
        ),
        vol.Required(CONF_ENABLE_ENHANCED_LIGHT_TRANSITION, default=False): cv.boolean,
        vol.Required(CONF_ENABLE_LIGHT_TRANSITIONING_FLAG, default=True): cv.boolean,
        vol.Required(CONF_ALWAYS_PREFER_XY_COLOR_MODE, default=True): cv.boolean,
        vol.Required(CONF_GROUP_MEMBERS_ASSUME_STATE, default=True): cv.boolean,
        vol.Required(CONF_ENABLE_IDENTIFY_ON_JOIN, default=True): cv.boolean,
        vol.Optional(
            CONF_CONSIDER_UNAVAILABLE_MAINS,
            default=CONF_DEFAULT_CONSIDER_UNAVAILABLE_MAINS,
        ): cv.positive_int,
        vol.Optional(
            CONF_CONSIDER_UNAVAILABLE_BATTERY,
            default=CONF_DEFAULT_CONSIDER_UNAVAILABLE_BATTERY,
        ): cv.positive_int,
    }
)

CONF_ZHA_ALARM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ALARM_MASTER_CODE, default="1234"): cv.string,
        vol.Required(CONF_ALARM_FAILED_TRIES, default=3): cv.positive_int,
        vol.Required(CONF_ALARM_ARM_REQUIRES_CODE, default=False): cv.boolean,
    }
)

CUSTOM_CONFIGURATION = "custom_configuration"

DATA_DEVICE_CONFIG = "zha_device_config"
DATA_ZHA = "zha"
DATA_ZHA_CONFIG = "config"
DATA_ZHA_BRIDGE_ID = "zha_bridge_id"
DATA_ZHA_CORE_EVENTS = "zha_core_events"
DATA_ZHA_GATEWAY = "zha_gateway"

DEBUG_COMP_BELLOWS = "bellows"
DEBUG_COMP_ZHA = "homeassistant.components.zha"
DEBUG_COMP_ZIGPY = "zigpy"
DEBUG_COMP_ZIGPY_ZNP = "zigpy_znp"
DEBUG_COMP_ZIGPY_DECONZ = "zigpy_deconz"
DEBUG_COMP_ZIGPY_XBEE = "zigpy_xbee"
DEBUG_COMP_ZIGPY_ZIGATE = "zigpy_zigate"
DEBUG_LEVEL_CURRENT = "current"
DEBUG_LEVEL_ORIGINAL = "original"
DEBUG_LEVELS = {
    DEBUG_COMP_BELLOWS: logging.DEBUG,
    DEBUG_COMP_ZHA: logging.DEBUG,
    DEBUG_COMP_ZIGPY: logging.DEBUG,
    DEBUG_COMP_ZIGPY_ZNP: logging.DEBUG,
    DEBUG_COMP_ZIGPY_DECONZ: logging.DEBUG,
    DEBUG_COMP_ZIGPY_XBEE: logging.DEBUG,
    DEBUG_COMP_ZIGPY_ZIGATE: logging.DEBUG,
}
DEBUG_RELAY_LOGGERS = [DEBUG_COMP_ZHA, DEBUG_COMP_ZIGPY]

DEFAULT_RADIO_TYPE = "ezsp"
DEFAULT_BAUDRATE = 57600
DEFAULT_DATABASE_NAME = "zigbee.db"

DEVICE_PAIRING_STATUS = "pairing_status"

DISCOVERY_KEY = "zha_discovery_info"

DOMAIN = "zha"

GROUP_ID = "group_id"
GROUP_IDS = "group_ids"
GROUP_NAME = "group_name"

MFG_CLUSTER_ID_START = 0xFC00

POWER_MAINS_POWERED = "Mains"
POWER_BATTERY_OR_UNKNOWN = "Battery or Unknown"

PRESET_SCHEDULE = "Schedule"
PRESET_COMPLEX = "Complex"
PRESET_TEMP_MANUAL = "Temporary manual"

ZHA_ALARM_OPTIONS = "zha_alarm_options"
ZHA_OPTIONS = "zha_options"

ZHA_CONFIG_SCHEMAS = {
    ZHA_OPTIONS: CONF_ZHA_OPTIONS_SCHEMA,
    ZHA_ALARM_OPTIONS: CONF_ZHA_ALARM_SCHEMA,
}

_ControllerClsType = type[zigpy.application.ControllerApplication]


class RadioType(enum.Enum):
    """Possible options for radio type."""

    ezsp = (
        "EZSP = Silicon Labs EmberZNet protocol: Elelabs, HUSBZB-1, Telegesis",
        bellows.zigbee.application.ControllerApplication,
    )
    znp = (
        "ZNP = Texas Instruments Z-Stack ZNP protocol: CC253x, CC26x2, CC13x2",
        zigpy_znp.zigbee.application.ControllerApplication,
    )
    deconz = (
        "deCONZ = dresden elektronik deCONZ protocol: ConBee I/II, RaspBee I/II",
        zigpy_deconz.zigbee.application.ControllerApplication,
    )
    zigate = (
        "ZiGate = ZiGate Zigbee radios: PiZiGate, ZiGate USB-TTL, ZiGate WiFi",
        zigpy_zigate.zigbee.application.ControllerApplication,
    )
    xbee = (
        "XBee = Digi XBee Zigbee radios: Digi XBee Series 2, 2C, 3",
        zigpy_xbee.zigbee.application.ControllerApplication,
    )

    @classmethod
    def list(cls) -> list[str]:
        """Return a list of descriptions."""
        return [e.description for e in RadioType]

    @classmethod
    def get_by_description(cls, description: str) -> RadioType:
        """Get radio by description."""
        for radio in cls:
            if radio.description == description:
                return radio
        raise ValueError

    def __init__(self, description: str, controller_cls: _ControllerClsType) -> None:
        """Init instance."""
        self._desc = description
        self._ctrl_cls = controller_cls

    @property
    def controller(self) -> _ControllerClsType:
        """Return controller class."""
        return self._ctrl_cls

    @property
    def description(self) -> str:
        """Return radio type description."""
        return self._desc


REPORT_CONFIG_ATTR_PER_REQ = 3
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
SENSOR_ELECTRICAL_MEASUREMENT = CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT
SENSOR_GENERIC = "generic"
SENSOR_HUMIDITY = CLUSTER_HANDLER_HUMIDITY
SENSOR_ILLUMINANCE = CLUSTER_HANDLER_ILLUMINANCE
SENSOR_METERING = "metering"
SENSOR_OCCUPANCY = CLUSTER_HANDLER_OCCUPANCY
SENSOR_OPENING = "opening"
SENSOR_PRESSURE = CLUSTER_HANDLER_PRESSURE
SENSOR_TEMPERATURE = CLUSTER_HANDLER_TEMPERATURE
SENSOR_TYPE = "sensor_type"

SIGNAL_ADD_ENTITIES = "zha_add_new_entities"
SIGNAL_ATTR_UPDATED = "attribute_updated"
SIGNAL_AVAILABLE = "available"
SIGNAL_MOVE_LEVEL = "move_level"
SIGNAL_REMOVE = "remove"
SIGNAL_SET_LEVEL = "set_level"
SIGNAL_STATE_ATTR = "update_state_attribute"
SIGNAL_UPDATE_DEVICE = "{}_zha_update_device"
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
ZHA_CLUSTER_HANDLER_MSG = "zha_channel_message"
ZHA_CLUSTER_HANDLER_MSG_BIND = "zha_channel_bind"
ZHA_CLUSTER_HANDLER_MSG_CFG_RPT = "zha_channel_configure_reporting"
ZHA_CLUSTER_HANDLER_MSG_DATA = "zha_channel_msg_data"
ZHA_CLUSTER_HANDLER_CFG_DONE = "zha_channel_cfg_done"
ZHA_CLUSTER_HANDLER_READS_PER_REQ = 5
ZHA_EVENT = "zha_event"
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


class Strobe(t.enum8):
    """Strobe enum."""

    No_Strobe = 0x00
    Strobe = 0x01


STARTUP_FAILURE_DELAY_S = 3
STARTUP_RETRIES = 3

EZSP_OVERWRITE_EUI64 = (
    "i_understand_i_can_update_eui64_only_once_and_i_still_want_to_do_it"
)
