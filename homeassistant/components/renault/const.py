"""Constants for the Renault component."""
DOMAIN = "renault"

CONF_LOCALE = "locale"
CONF_KAMEREON_ACCOUNT_ID = "kamereon_account_id"

DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

PLATFORMS = [
    "sensor",
]

DEVICE_CLASS_PLUG_STATE = "renault__plug_state"
DEVICE_CLASS_CHARGE_STATE = "renault__charge_state"
DEVICE_CLASS_CHARGE_MODE = "renault__charge_mode"
