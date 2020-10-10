"""Constants for RFXtrx integration."""

CONF_FIRE_EVENT = "fire_event"
CONF_DATA_BITS = "data_bits"
CONF_AUTOMATIC_ADD = "automatic_add"
CONF_SIGNAL_REPETITIONS = "signal_repetitions"
CONF_DEBUG = "debug"
CONF_OFF_DELAY = "off_delay"

CONF_REMOVE_DEVICE = "remove_device"
CONF_REPLACE_DEVICE = "replace_device"

COMMAND_ON_LIST = [
    "On",
    "Up",
    "Stop",
    "Open (inline relay)",
    "Stop (inline relay)",
    "Enable sun automation",
]

COMMAND_OFF_LIST = [
    "Off",
    "Down",
    "Close (inline relay)",
    "Disable sun automation",
]

ATTR_EVENT = "event"

SERVICE_SEND = "send"

DEVICE_PACKET_TYPE_LIGHTING4 = 0x13

EVENT_RFXTRX_EVENT = "rfxtrx_event"
