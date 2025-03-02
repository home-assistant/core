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
ATTR_LAST_EVENT_INFO = "last_event_info"
ATTR_LAST_EVENT_SENSOR_NAME = "last_event_sensor_name"
ATTR_LAST_EVENT_SENSOR_TYPE = "last_event_sensor_type"
ATTR_LAST_EVENT_TIMESTAMP = "last_event_timestamp"
ATTR_LIGHT = "light"
ATTR_SYSTEM_ID = "system_id"
ATTR_VOICE_PROMPT_VOLUME = "voice_prompt_volume"

DISPATCHER_TOPIC_WEBSOCKET_EVENT = "simplisafe_websocket_event_{0}"
