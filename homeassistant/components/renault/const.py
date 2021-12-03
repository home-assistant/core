"""Constants for the Renault component."""
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

DOMAIN = "renault"

CONF_LOCALE = "locale"
CONF_KAMEREON_ACCOUNT_ID = "kamereon_account_id"

DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

PLATFORMS = [
    BINARY_SENSOR_DOMAIN,
    BUTTON_DOMAIN,
    DEVICE_TRACKER_DOMAIN,
    SELECT_DOMAIN,
    SENSOR_DOMAIN,
]

DEVICE_CLASS_PLUG_STATE = "renault__plug_state"
DEVICE_CLASS_CHARGE_STATE = "renault__charge_state"
DEVICE_CLASS_CHARGE_MODE = "renault__charge_mode"
