"""Define constants for the SimpliSafe component."""
from datetime import timedelta
import logging

from simplipy.system.v3 import VOLUME_HIGH, VOLUME_LOW, VOLUME_MEDIUM, VOLUME_OFF

LOGGER = logging.getLogger(__package__)

DOMAIN = "simplisafe"

CONF_AUTH_CODE = "auth_code"
CONF_USER_ID = "user_id"

DATA_CLIENT = "client"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

ATTR_ALARM_DURATION = "alarm_duration"
ATTR_ALARM_VOLUME = "alarm_volume"
ATTR_CHIME_VOLUME = "chime_volume"
ATTR_ENTRY_DELAY_AWAY = "entry_delay_away"
ATTR_ENTRY_DELAY_HOME = "entry_delay_home"
ATTR_EXIT_DELAY_AWAY = "exit_delay_away"
ATTR_EXIT_DELAY_HOME = "exit_delay_home"
ATTR_LIGHT = "light"
ATTR_VOICE_PROMPT_VOLUME = "voice_prompt_volume"

VOLUMES = [VOLUME_OFF, VOLUME_LOW, VOLUME_MEDIUM, VOLUME_HIGH]
VOLUME_STRING_MAP = {
    VOLUME_HIGH: "high",
    VOLUME_LOW: "low",
    VOLUME_MEDIUM: "medium",
    VOLUME_OFF: "off",
}
