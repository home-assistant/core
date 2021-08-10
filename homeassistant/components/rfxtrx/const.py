"""Constants for RFXtrx integration."""

CONF_FIRE_EVENT = "fire_event"
CONF_DATA_BITS = "data_bits"
CONF_AUTOMATIC_ADD = "automatic_add"
CONF_SIGNAL_REPETITIONS = "signal_repetitions"
CONF_DEBUG = "debug"
CONF_OFF_DELAY = "off_delay"
CONF_VENETIAN_BLIND_MODE = "venetian_blind_mode"

CONF_REMOVE_DEVICE = "remove_device"
CONF_REPLACE_DEVICE = "replace_device"

CONST_VENETIAN_BLIND_MODE_DEFAULT = "Unknown"
CONST_VENETIAN_BLIND_MODE_EU = "EU"
CONST_VENETIAN_BLIND_MODE_US = "US"

COMMAND_ON_LIST = [
    "On",
    "Up",
    "Stop",
    "Group on",
    "Open (inline relay)",
    "Stop (inline relay)",
    "Enable sun automation",
]

COMMAND_OFF_LIST = [
    "Off",
    "Group off",
    "Down",
    "Close (inline relay)",
    "Disable sun automation",
]

COMMAND_GROUP_LIST = [
    "Group on",
    "Group off",
]

ATTR_EVENT = "event"

SERVICE_SEND = "send"

DEVICE_PACKET_TYPE_LIGHTING4 = 0x13

EVENT_RFXTRX_EVENT = "rfxtrx_event"

DATA_RFXOBJECT = "rfxobject"
DATA_LISTENER = "ha_stop"
DATA_CLEANUP_CALLBACKS = "cleanup_callbacks"
