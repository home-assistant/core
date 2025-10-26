"""Constants for Video Guard integration."""
import logging
from typing import Final

DOMAIN = "guarddionisis"

LOGGER = logging.getLogger(__package__)

CONF_ID = "id"
CONF_TYPE = "type"

SERVICE_SET_ALARM_STATUS = "set_alarm_status"
SERVICE_CLEAR_VIDEOS = "clear_videos"
SERVICE_SET_COUNTER = "set_counter"
SERVICE_INCREMENT_COUNTER = "increment_counter"
SERVICE_DEINCREMENT_COUNTER = "deincrement_counter"

ATTR_ALARM_STATUS: Final = "alarm_status"
ATTR_COUNTER_VALUE: Final = "value"