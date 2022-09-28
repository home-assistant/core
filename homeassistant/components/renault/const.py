"""Constants for the Renault component."""
from homeassistant.const import Platform

DOMAIN = "renault"

CONF_LOCALE = "locale"
CONF_KAMEREON_ACCOUNT_ID = "kamereon_account_id"

DEFAULT_SCAN_INTERVAL = 420  # 7 minutes

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SELECT,
    Platform.SENSOR,
]

DEVICE_CLASS_PLUG_STATE = "renault__plug_state"
DEVICE_CLASS_CHARGE_STATE = "renault__charge_state"
DEVICE_CLASS_CHARGE_MODE = "renault__charge_mode"
