"""Constants for the Flic Button integration."""

from typing import Final

from pyflic_ble import DeviceType

DOMAIN: Final = "flic_button"

DEVICE_TYPE_MODEL_NAMES: Final = {
    DeviceType.FLIC2: "Flic 2",
    DeviceType.DUO: "Flic Duo",
    DeviceType.TWIST: "Flic Twist",
}

CONF_PAIRING_ID: Final = "pairing_id"
CONF_PAIRING_KEY: Final = "pairing_key"
CONF_SERIAL_NUMBER: Final = "serial_number"
CONF_DEVICE_TYPE: Final = "device_type"
# The Ed25519 signature variant found when pairing a Twist, 0 for other buttons
CONF_SIG_BITS: Final = "sig_bits"

EVENT_CLASS_BUTTON: Final = "button"

CONF_PUSH_TWIST_MODE: Final = "push_twist_mode"
