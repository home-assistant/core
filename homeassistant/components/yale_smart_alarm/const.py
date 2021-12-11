"""Yale integration constants."""
import logging

from yalesmartalarmclient.client import (
    YALE_STATE_ARM_FULL,
    YALE_STATE_ARM_PARTIAL,
    YALE_STATE_DISARM,
)

from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)

CONF_AREA_ID = "area_id"
DEFAULT_NAME = "Yale Smart Alarm"
DEFAULT_AREA_ID = "1"

MANUFACTURER = "Yale"
MODEL = "main"

DOMAIN = "yale_smart_alarm"
COORDINATOR = "coordinator"

DEFAULT_SCAN_INTERVAL = 15

LOGGER = logging.getLogger(__package__)

ATTR_ONLINE = "online"
ATTR_STATUS = "status"

PLATFORMS = ["alarm_control_panel"]

STATE_MAP = {
    YALE_STATE_DISARM: STATE_ALARM_DISARMED,
    YALE_STATE_ARM_PARTIAL: STATE_ALARM_ARMED_HOME,
    YALE_STATE_ARM_FULL: STATE_ALARM_ARMED_AWAY,
}
