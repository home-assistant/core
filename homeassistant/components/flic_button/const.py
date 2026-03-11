"""Constants for the Flic Button integration."""

from __future__ import annotations

from typing import Final

from pyflic_ble import DeviceType, PushTwistMode
from pyflic_ble.const import (  # noqa: F401
    EVENT_TYPE_CLICK,
    EVENT_TYPE_DOUBLE_CLICK,
    EVENT_TYPE_DOWN,
    EVENT_TYPE_HOLD,
    EVENT_TYPE_PUSH_TWIST_DECREMENT,
    EVENT_TYPE_PUSH_TWIST_INCREMENT,
    EVENT_TYPE_ROTATE_CLOCKWISE,
    EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE,
    EVENT_TYPE_SELECTOR_CHANGED,
    EVENT_TYPE_SWIPE_DOWN,
    EVENT_TYPE_SWIPE_LEFT,
    EVENT_TYPE_SWIPE_RIGHT,
    EVENT_TYPE_SWIPE_UP,
    EVENT_TYPE_TWIST_DECREMENT,
    EVENT_TYPE_TWIST_INCREMENT,
    EVENT_TYPE_UP,
    FLIC_SERVICE_UUID,
    PAIRING_TIMEOUT,
    TWIST_SERVICE_UUID,
)

__all__ = [
    "DeviceType",
    "PushTwistMode",
]

DOMAIN: Final = "flic_button"

DEVICE_TYPE_MODEL_NAMES: Final = {
    DeviceType.FLIC2: "Flic 2",
    DeviceType.DUO: "Flic Duo",
    DeviceType.TWIST: "Flic Twist",
}

# Config entry data keys
CONF_PAIRING_ID: Final = "pairing_id"
CONF_PAIRING_KEY: Final = "pairing_key"
CONF_SERIAL_NUMBER: Final = "serial_number"
CONF_BATTERY_LEVEL: Final = "battery_level"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_SIG_BITS: Final = (
    "sig_bits"  # Ed25519 signature variant (0-3) for Twist quick verify
)

# Event classes
EVENT_CLASS_BUTTON: Final = "button"

# Flic event domain
FLIC_BUTTON_EVENT: Final = f"{DOMAIN}_event"

# Options constants
CONF_PUSH_TWIST_MODE: Final = "push_twist_mode"
