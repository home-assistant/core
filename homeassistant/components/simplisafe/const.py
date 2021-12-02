"""Define constants for the SimpliSafe component."""
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "simplisafe"

ATTR_ALARM_DURATION = "alarm_duration"
ATTR_ALARM_VOLUME = "alarm_volume"
ATTR_CHIME_VOLUME = "chime_volume"
ATTR_ENTRY_DELAY_AWAY = "entry_delay_away"
ATTR_ENTRY_DELAY_HOME = "entry_delay_home"
ATTR_EXIT_DELAY_AWAY = "exit_delay_away"
ATTR_EXIT_DELAY_HOME = "exit_delay_home"
ATTR_LIGHT = "light"
ATTR_VOICE_PROMPT_VOLUME = "voice_prompt_volume"

CONF_USER_ID = "user_id"

DATA_CLIENT = "client"
