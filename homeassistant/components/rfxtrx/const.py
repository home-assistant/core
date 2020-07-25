"""Constants for RFXtrx integration."""


COMMAND_ON_LIST = [
    "On",
    "Up",
    "Stop",
    "Open (inline relay)",
    "Stop (inline relay)",
]

COMMAND_OFF_LIST = [
    "Off",
    "Down",
    "Close (inline relay)",
]

ATTR_EVENT = "event"

SERVICE_SEND = "send"

DEVICE_PACKET_TYPE_LIGHTING4 = 0x13

EVENT_RFXTRX_EVENT = "rfxtrx_event"
