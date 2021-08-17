"""Constants for the Renault component."""
DOMAIN = "renault"

CONF_LOCALE = "locale"
CONF_KAMEREON_ACCOUNT_ID = "kamereon_account_id"

DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

REGEX_VIN = "(?i)^VF1[\\w]{14}$"

PLATFORMS = [
    "sensor",
]

DEVICE_CLASS_PLUG_STATE = "renault__plug_state"
DEVICE_CLASS_CHARGE_STATE = "renault__charge_state"
DEVICE_CLASS_CHARGE_MODE = "renault__charge_mode"

SERVICE_AC_CANCEL = "ac_cancel"
SERVICE_AC_START = "ac_start"
SERVICE_CHARGE_SET_MODE = "charge_set_mode"
SERVICE_CHARGE_SET_SCHEDULES = "charge_set_schedules"
SERVICE_CHARGE_START = "charge_start"
SERVICES = [
    SERVICE_AC_CANCEL,
    SERVICE_AC_START,
    SERVICE_CHARGE_SET_MODE,
    SERVICE_CHARGE_SET_SCHEDULES,
    SERVICE_CHARGE_START,
]
