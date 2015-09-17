"""
homeassistant.components.automation.time
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Offers time listening automation rules.
"""
import logging

from homeassistant.util import convert
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
    """ Listen for state changes based on `config`. """
    if CONF_AFTER in config:
        after = dt_util.parse_time_str(config[CONF_AFTER])
        if after is None:
            _LOGGER.error(
                'Received invalid after value: %s', config[CONF_AFTER])
            return False
        hours, minutes, seconds = after.hour, after.minute, after.second
    elif CONF_HOURS in config or CONF_MINUTES in config \
         or CONF_SECONDS in config:
        hours = convert(config.get(CONF_HOURS), int)
        minutes = convert(config.get(CONF_MINUTES), int)
        seconds = convert(config.get(CONF_SECONDS), int)
    else:
        _LOGGER.error('One of %s, %s, %s OR %s needs to be specified',
            CONF_HOURS, CONF_MINUTES, CONF_SECONDS, CONF_AFTER)
        return False

    def time_automation_listener(now):
        """ Listens for time changes and calls action. """
        action()

    track_time_change(hass, time_automation_listener,
                      hour=hours, minute=minutes, second=seconds)

    return True


def if_action(hass, config):
    """ Wraps action method with time based condition. """
    before = config.get(CONF_BEFORE)
    after = config.get(CONF_AFTER)
    weekday = config.get(CONF_WEEKDAY)

    if before is None and after is None and weekday is None:
        logging.getLogger(__name__).error(
            "Missing if-condition configuration key %s, %s or %s",
            CONF_BEFORE, CONF_AFTER, CONF_WEEKDAY)
        return None

    def time_if():
        """ Validate time based if-condition """
        now = dt_util.now()
        if before is not None:
            time = dt_util.parse_time_str(before)
            if time is None:
                return False

            before_point = now.replace(hour=time.hour, minute=time.minute)

            if now > before_point:
                return False

        if after is not None:
            time = dt_util.parse_time_str(after)
            if time is None:
                return False

            after_point = now.replace(hour=time.hour, minute=time.minute)

            if now < after_point:
                return False

        if weekday is not None:
            now_weekday = WEEKDAYS[now.weekday()]

            if isinstance(weekday, str) and weekday != now_weekday or \
               now_weekday not in weekday:
                return False

        return True

    return time_if
