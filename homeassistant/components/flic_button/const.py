"""Constants for the Flic Button integration."""

from __future__ import annotations

from typing import Final

from pyflic_ble import DeviceType

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
