"""Yale integration constants."""
import logging
from typing import Final

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

CONF_AREA_ID: Final = "area_id"
DEFAULT_NAME: Final = "Yale Smart Alarm"
DEFAULT_AREA_ID: Final = "1"

MANUFACTURER: Final = "Yale"
MODEL: Final = "main"

DOMAIN: Final = "yale_smart_alarm"
COORDINATOR: Final = "coordinator"

DEFAULT_SCAN_INTERVAL: int = 15

LOGGER = logging.getLogger(__name__)

ATTR_ONLINE: Final = "online"
ATTR_STATUS: Final = "status"
ATTR_VIA_DEVICE: Final = "via_device"

PLATFORMS = ["alarm_control_panel", "lock"]

STATE_MAP = {
    YALE_STATE_DISARM: STATE_ALARM_DISARMED,
    YALE_STATE_ARM_PARTIAL: STATE_ALARM_ARMED_HOME,
    YALE_STATE_ARM_FULL: STATE_ALARM_ARMED_AWAY,
}
