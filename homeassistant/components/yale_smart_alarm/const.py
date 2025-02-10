"""Yale integration constants."""

import logging

from yalesmartalarmclient.client import (
    YALE_STATE_ARM_FULL,
    YALE_STATE_ARM_PARTIAL,
    YALE_STATE_DISARM,
)
from yalesmartalarmclient.exceptions import AuthenticationError, UnknownError

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import Platform

CONF_AREA_ID = "area_id"
CONF_LOCK_CODE_DIGITS = "lock_code_digits"
DEFAULT_NAME = "Yale Smart Alarm"
DEFAULT_AREA_ID = "1"
DEFAULT_LOCK_CODE_DIGITS = 4

MANUFACTURER = "Yale"
MODEL = "main"

DOMAIN = "yale_smart_alarm"

DEFAULT_SCAN_INTERVAL = 15

LOGGER = logging.getLogger(__package__)

ATTR_ONLINE = "online"
ATTR_STATUS = "status"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LOCK,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

STATE_MAP = {
    YALE_STATE_DISARM: AlarmControlPanelState.DISARMED,
    YALE_STATE_ARM_PARTIAL: AlarmControlPanelState.ARMED_HOME,
    YALE_STATE_ARM_FULL: AlarmControlPanelState.ARMED_AWAY,
}

YALE_BASE_ERRORS = (
    ConnectionError,
    TimeoutError,
    UnknownError,
)
YALE_ALL_ERRORS = (*YALE_BASE_ERRORS, AuthenticationError)
