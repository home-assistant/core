"""
Offer time listening automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#time-trigger
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_AFTER, CONF_PLATFORM
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change

CONF_DATE = "date"
CONF_HOURS = "hours"
CONF_MINUTES = "minutes"
CONF_SECONDS = "seconds"

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_PLATFORM): 'time',
    CONF_DATE: cv.date,
    CONF_AFTER: cv.time,
    CONF_HOURS: vol.Any(vol.Coerce(int), vol.Coerce(str)),
    CONF_MINUTES: vol.Any(vol.Coerce(int), vol.Coerce(str)),
    CONF_SECONDS: vol.Any(vol.Coerce(int), vol.Coerce(str)),
}), cv.has_at_least_one_key(CONF_DATE,CONF_HOURS, CONF_MINUTES,
                            CONF_SECONDS, CONF_AFTER))


def async_trigger(hass, config, action):
    """Listen for state changes based on configuration."""
    bflag =0;
    if CONF_DATE in config:
        date = config.get(CONF_DATE)
        years,months,days = date.year,date.month,date.day#v
        bflag =1;
    if CONF_AFTER in config:
        after = config.get(CONF_AFTER)
        hours, minutes, seconds = after.hour, after.minute, after.second
    else:
        hours = config.get(CONF_HOURS)
        minutes = config.get(CONF_MINUTES)
        seconds = config.get(CONF_SECONDS)

    @callback
    def time_automation_listener(now):
        """Listen for time changes and calls action."""
        hass.async_run_job(action, {
            'trigger': {
                'platform': 'time',
                'now': now,
            },
        })
    if (bflag ==1):
        return async_track_time_change(hass, time_automation_listener,year=years,month=months,day=days,
                                   hour=hours, minute=minutes, second=seconds)
    else:
        return async_track_time_change(hass, time_automation_listener,
                                   hour=hours, minute=minutes, second=seconds)

