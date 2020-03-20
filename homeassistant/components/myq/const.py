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
