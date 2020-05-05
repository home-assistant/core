"""Constants for the BleBox devices integration."""

from homeassistant.components.cover import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GATE,
    DEVICE_CLASS_SHUTTER,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)

DOMAIN = "blebox"
PRODUCT = "product"

DEFAULT_SETUP_TIMEOUT = 3

# translation strings
ADDRESS_ALREADY_CONFIGURED = "address_already_configured"
CANNOT_CONNECT = "cannot_connect"
UNSUPPORTED_VERSION = "unsupported_version"
UNKNOWN = "unknown"

BLEBOX_TO_HASS_DEVICE_CLASSES = {
    "shutter": DEVICE_CLASS_SHUTTER,
    "gatebox": DEVICE_CLASS_DOOR,
    "gate": DEVICE_CLASS_GATE,
}

BLEBOX_TO_HASS_COVER_STATES = {
    None: None,
    0: STATE_CLOSING,  # moving down
    1: STATE_OPENING,  # moving up
    2: STATE_OPEN,  # manually stopped
    3: STATE_CLOSED,  # lower limit
    4: STATE_OPEN,  # upper limit / open
    # gateController
    5: STATE_OPEN,  # overload
    6: STATE_OPEN,  # motor failure
    # 7 is not used
    8: STATE_OPEN,  # safety stop
}

DEFAULT_HOST = "192.168.0.2"
DEFAULT_PORT = 80
