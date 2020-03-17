"""The MyQ integration."""
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING

DOMAIN = "myq"

PLATFORMS = ["cover"]

MYQ_DEVICE_TYPE = "device_type"
MYQ_DEVICE_TYPE_GATE = "gate"
MYQ_DEVICE_STATE = "state"
MYQ_DEVICE_STATE_ONLINE = "online"

MYQ_TO_HASS = {
    "closed": STATE_CLOSED,
    "closing": STATE_CLOSING,
    "open": STATE_OPEN,
    "opening": STATE_OPENING,
}

GATE_STATE_ICONS = {
    STATE_CLOSED: "mdi:gate",
    STATE_CLOSING: "mdi:gate-arrow-right",
    STATE_OPENING: "mdi:gate-arrow-right",
    STATE_OPEN: "mdi:gate-open",
}

GARAGE_STATE_ICONS = {
    STATE_CLOSED: "mdi:garage-variant",
    STATE_CLOSING: "mdi:arrow-down-bold-box",
    STATE_OPENING: "mdi:arrow-up-bold-box",
    STATE_OPEN: "mdi:garage-open-variant",
}
