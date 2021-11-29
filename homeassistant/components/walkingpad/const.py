"""Constants for the WalkingPad component."""
from typing import Final

ATTR_MODE: Final = "mode"
ATTR_SPEED: Final = "speed"

AWAIT_SLEEP_INTERVAL: Final = 0.7

CONF_CONN_TYPE: Final = "conn_type"
CONF_DEFAULT_SPEED: Final = "default_speed"
CONF_TYPE_BLE: Final = "ble"
CONF_TYPE_WIFI: Final = "wifi"
CONF_UUID: Final = "uuid"

DEFAULT_NAME: Final = "Walking Pad"
DEFAULT_SPEED: Final = 2.0
DEFAULT_STATUS: Final = "off"

DOMAIN: Final = "walkingpad"

MAX_SPEED: Final = 6.0
MIN_SPEED: Final = 0.0
MODES_DICT: Final = {0: "auto", 1: "manual", 2: "standby"}

SERVICE_SET_MODE: Final = "set_mode"
SERVICE_SET_SPEED_USER: Final = "set_speed_user"
SERVICE_SET_SPEED: Final = "set_speed"
SERVICE_START_BELT: Final = "start_belt"
SERVICE_STOP_BELT: Final = "stop_belt"
