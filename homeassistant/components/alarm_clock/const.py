"""Constants for the Alarm Clock integration."""

import voluptuous as vol

from homeassistant.const import CONF_ICON, CONF_NAME
import homeassistant.helpers.config_validation as cv

DOMAIN = "alarm_clock"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

ATTR_ALARM_TIME = "alarm_time"
ATTR_REPEAT_DAYS = "repeat_days"
ATTR_NEXT_ALARM = "next_alarm"

CONF_ALARM_TIME = "alarm_time"
CONF_REPEAT_DAYS = "repeat_days"

EVENT_ALARM_CLOCK_STARTED = "alarm_clock.started"
EVENT_ALARM_CLOCK_FINISHED = "alarm_clock.finished"
EVENT_ALARM_CLOCK_CANCELLED = "alarm_clock.cancelled"
EVENT_ALARM_CLOCK_CHANGED = "alarm_clock.changed"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

STORAGE_FIELDS = {
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Required(CONF_ALARM_TIME): cv.time,
    vol.Required(CONF_REPEAT_DAYS): cv.weekdays,
}
