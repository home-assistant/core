"""Constants for the NeoPool integration."""

from homeassistant.const import Platform

DOMAIN = "neopool"
NAME = "NeoPool"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

DEFAULT_SCAN_INTERVAL = 20  # in seconds
FOLLOW_UP_REFRESH_DELAY = 2.0  # seconds  (delay before a 2nd refresh for IO entity)
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1

CONF_UNIT_ID = "unit_id"
CONF_MODBUS_FRAMER = "modbus_framer"

CONF_USE_LIGHT = "use_light"
CONF_USE_COVER_SENSOR = "use_cover_sensor"
CONF_USE_AUX1 = "use_aux1"
CONF_USE_AUX2 = "use_aux2"
CONF_USE_AUX3 = "use_aux3"
CONF_USE_AUX4 = "use_aux4"

CURRENT_VERSION = 6

PERIOD_MAP = {
    "1_day": 86400,
    "2_days": 2 * 86400,
    "3_days": 3 * 86400,
    "4_days": 4 * 86400,
    "5_days": 5 * 86400,
    "1_week": 7 * 86400,
    "2_weeks": 14 * 86400,
    "3_weeks": 21 * 86400,
    "4_weeks": 28 * 86400,
}

PERIOD_SECONDS_TO_KEY = {v: k for k, v in PERIOD_MAP.items()}
