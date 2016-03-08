"""
Offer time listening automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#time-trigger
"""
import logging

import homeassistant.util.dt as dt_util
from homeassistant.helpers.event import track_time_change

CONF_HOURS = "hours"
CONF_MINUTES = "minutes"
CONF_SECONDS = "seconds"
CONF_BEFORE = "before"
CONF_AFTER = "after"
CONF_WEEKDAY = "weekday"

WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

_LOGGER = logging.getLogger(__name__)


def trigger(hass, config, action):
    """Listen for state changes based on configuration."""
    if CONF_AFTER in config:
        after = dt_util.parse_time_str(config[CONF_AFTER])
        if after is None:
            _error_time(config[CONF_AFTER], CONF_AFTER)
            return False
        hours, minutes, seconds = after.hour, after.minute, after.second
    elif (CONF_HOURS in config or CONF_MINUTES in config or
          CONF_SECONDS in config):
        hours = config.get(CONF_HOURS)
        minutes = config.get(CONF_MINUTES)
        seconds = config.get(CONF_SECONDS)
    else:
        _LOGGER.error('One of %s, %s, %s OR %s needs to be specified',
                      CONF_HOURS, CONF_MINUTES, CONF_SECONDS, CONF_AFTER)
        return False

    def time_automation_listener(now):
        """Listen for time changes and calls action."""
        action()

    track_time_change(hass, time_automation_listener,
                      hour=hours, minute=minutes, second=seconds)

    return True


def if_action(hass, config):
    """Wrap action method with time based condition."""
    before = config.get(CONF_BEFORE)
    after = config.get(CONF_AFTER)
    weekday = config.get(CONF_WEEKDAY)

    if before is None and after is None and weekday is None:
        _LOGGER.error(
            "Missing if-condition configuration key %s, %s or %s",
            CONF_BEFORE, CONF_AFTER, CONF_WEEKDAY)
        return None

    if before is not None:
        before = dt_util.parse_time_str(before)
        if before is None:
            _error_time(before, CONF_BEFORE)
            return None

    if after is not None:
        after = dt_util.parse_time_str(after)
        if after is None:
            _error_time(after, CONF_AFTER)
            return None

    def time_if():
        """Validate time based if-condition."""
        now = dt_util.now()
        if before is not None and now > now.replace(hour=before.hour,
                                                    minute=before.minute):
            return False

        if after is not None and now < now.replace(hour=after.hour,
                                                   minute=after.minute):
            return False

        if weekday is not None:
            now_weekday = WEEKDAYS[now.weekday()]

            if isinstance(weekday, str) and weekday != now_weekday or \
               now_weekday not in weekday:
                return False

        return True

    return time_if


def _error_time(value, key):
    """Helper method to print error."""
    _LOGGER.error(
        "Received invalid value for '%s': %s", key, value)
    if isinstance(value, int):
        _LOGGER.error('Make sure you wrap time values in quotes')
