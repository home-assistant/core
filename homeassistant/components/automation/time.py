"""
homeassistant.components.automation.time
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Offers time listening automation rules.
"""
import logging

from homeassistant.util import convert
import homeassistant.util.dt as dt_util
from homeassistant.helpers.event import track_time_change

CONF_HOURS = "time_hours"
CONF_MINUTES = "time_minutes"
CONF_SECONDS = "time_seconds"
CONF_BEFORE = "before"
CONF_AFTER = "after"
CONF_WEEKDAY = "weekday"

WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


def trigger(hass, config, action):
    """ Listen for state changes based on `config`. """
    hours = convert(config.get(CONF_HOURS), int)
    minutes = convert(config.get(CONF_MINUTES), int)
    seconds = convert(config.get(CONF_SECONDS), int)

    def time_automation_listener(now):
        """ Listens for time changes and calls action. """
        action()

    track_time_change(hass, time_automation_listener,
                      hour=hours, minute=minutes, second=seconds)

    return True


def if_action(hass, config, action):
    """ Wraps action method with time based condition. """
    before = config.get(CONF_BEFORE)
    after = config.get(CONF_AFTER)
    weekday = config.get(CONF_WEEKDAY)

    if before is None and after is None and weekday is None:
        logging.getLogger(__name__).error(
            "Missing if-condition configuration key %s, %s or %s",
            CONF_BEFORE, CONF_AFTER, CONF_WEEKDAY)

    def time_if():
        """ Validate time based if-condition """
        now = dt_util.now()

        if before is not None:
            # Strip seconds if given
            before_h, before_m = before.split(':')[0:2]

            before_point = now.replace(hour=int(before_h),
                                       minute=int(before_m))

            if now > before_point:
                return

        if after is not None:
            # Strip seconds if given
            after_h, after_m = after.split(':')[0:2]

            after_point = now.replace(hour=int(after_h), minute=int(after_m))

            if now < after_point:
                return

        if weekday is not None:
            now_weekday = WEEKDAYS[now.weekday()]

            if isinstance(weekday, str) and weekday != now_weekday or \
               now_weekday not in weekday:
                return

        action()

    return time_if
