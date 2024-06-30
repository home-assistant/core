"""Constants for history_stats."""

from homeassistant.const import Platform

PLATFORMS = [Platform.SENSOR]
DOMAIN = "history_stats"
DEFAULT_NAME = "unnamed history stats"

CONF_START = "start"
CONF_END = "end"
CONF_DURATION = "duration"
CONF_PERIOD_KEYS = [CONF_START, CONF_END, CONF_DURATION]

CONF_TYPE_TIME = "time"
CONF_TYPE_RATIO = "ratio"
CONF_TYPE_COUNT = "count"
CONF_TYPE_KEYS = [CONF_TYPE_TIME, CONF_TYPE_RATIO, CONF_TYPE_COUNT]
