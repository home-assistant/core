"""
homeassistant.components.automation.sun
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Offers sun based automation rules.
"""
import logging
from datetime import timedelta

from homeassistant.components import sun
from homeassistant.helpers.event import track_point_in_utc_time
import homeassistant.util.dt as dt_util

DEPENDENCIES = ['sun']

CONF_OFFSET = 'offset'
CONF_EVENT = 'event'

EVENT_SUNSET = 'sunset'
EVENT_SUNRISE = 'sunrise'

_LOGGER = logging.getLogger(__name__)


def trigger(hass, config, action):
    """ Listen for events based on config. """
    event = config.get(CONF_EVENT)

    if event is None:
        _LOGGER.error("Missing configuration key %s", CONF_EVENT)
        return False

    event = event.lower()
    if event not in (EVENT_SUNRISE, EVENT_SUNSET):
        _LOGGER.error("Invalid value for %s: %s", CONF_EVENT, event)
        return False

    if CONF_OFFSET in config:
        raw_offset = config.get(CONF_OFFSET)

        negative_offset = False
        if raw_offset.startswith('-'):
            negative_offset = True
            raw_offset = raw_offset[1:]

        try:
            (hour, minute, second) = [int(x) for x in raw_offset.split(':')]
        except ValueError:
            _LOGGER.error('Could not parse offset %s', raw_offset)
            return False

        offset = timedelta(hours=hour, minutes=minute, seconds=second)

        if negative_offset:
            offset *= -1
    else:
        offset = timedelta(0)

    # Do something to call action
    if event == EVENT_SUNRISE:
        trigger_sunrise(hass, action, offset)
    else:
        trigger_sunset(hass, action, offset)

    return True


def trigger_sunrise(hass, action, offset):
    """ Trigger action at next sun rise. """
    def next_rise():
        """ Returns next sunrise. """
        next_time = sun.next_rising_utc(hass) + offset

        while next_time < dt_util.utcnow():
            next_time = next_time + timedelta(days=1)

        return next_time

    def sunrise_automation_listener(now):
        """ Called when it's time for action. """
        track_point_in_utc_time(hass, sunrise_automation_listener, next_rise())
        action()

    track_point_in_utc_time(hass, sunrise_automation_listener, next_rise())


def trigger_sunset(hass, action, offset):
    """ Trigger action at next sun set. """
    def next_set():
        """ Returns next sunrise. """
        next_time = sun.next_setting_utc(hass) + offset

        while next_time < dt_util.utcnow():
            next_time = next_time + timedelta(days=1)

        return next_time

    def sunset_automation_listener(now):
        """ Called when it's time for action. """
        track_point_in_utc_time(hass, sunset_automation_listener, next_set())
        action()

    track_point_in_utc_time(hass, sunset_automation_listener, next_set())
