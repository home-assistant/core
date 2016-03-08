"""
Offer sun based automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#sun-trigger
"""
import logging
from datetime import timedelta

import homeassistant.util.dt as dt_util
from homeassistant.components import sun
from homeassistant.helpers.event import track_sunrise, track_sunset

DEPENDENCIES = ['sun']

CONF_OFFSET = 'offset'
CONF_EVENT = 'event'
CONF_BEFORE = "before"
CONF_BEFORE_OFFSET = "before_offset"
CONF_AFTER = "after"
CONF_AFTER_OFFSET = "after_offset"

EVENT_SUNSET = 'sunset'
EVENT_SUNRISE = 'sunrise'

_LOGGER = logging.getLogger(__name__)


def trigger(hass, config, action):
    """Listen for events based on configuration."""
    event = config.get(CONF_EVENT)

    if event is None:
        _LOGGER.error("Missing configuration key %s", CONF_EVENT)
        return False

    event = event.lower()
    if event not in (EVENT_SUNRISE, EVENT_SUNSET):
        _LOGGER.error("Invalid value for %s: %s", CONF_EVENT, event)
        return False

    offset = _parse_offset(config.get(CONF_OFFSET))
    if offset is False:
        return False

    # Do something to call action
    if event == EVENT_SUNRISE:
        track_sunrise(hass, action, offset)
    else:
        track_sunset(hass, action, offset)

    return True


def if_action(hass, config):
    """Wrap action method with sun based condition."""
    before = config.get(CONF_BEFORE)
    after = config.get(CONF_AFTER)

    # Make sure required configuration keys are present
    if before is None and after is None:
        logging.getLogger(__name__).error(
            "Missing if-condition configuration key %s or %s",
            CONF_BEFORE, CONF_AFTER)
        return None

    # Make sure configuration keys have the right value
    if before not in (None, EVENT_SUNRISE, EVENT_SUNSET) or \
       after not in (None, EVENT_SUNRISE, EVENT_SUNSET):
        logging.getLogger(__name__).error(
            "%s and %s can only be set to %s or %s",
            CONF_BEFORE, CONF_AFTER, EVENT_SUNRISE, EVENT_SUNSET)
        return None

    before_offset = _parse_offset(config.get(CONF_BEFORE_OFFSET))
    after_offset = _parse_offset(config.get(CONF_AFTER_OFFSET))
    if before_offset is False or after_offset is False:
        return None

    if before is None:
        def before_func():
            """Return no point in time."""
            return None
    elif before == EVENT_SUNRISE:
        def before_func():
            """Return time before sunrise."""
            return sun.next_rising(hass) + before_offset
    else:
        def before_func():
            """Return time before sunset."""
            return sun.next_setting(hass) + before_offset

    if after is None:
        def after_func():
            """Return no point in time."""
            return None
    elif after == EVENT_SUNRISE:
        def after_func():
            """Return time after sunrise."""
            return sun.next_rising(hass) + after_offset
    else:
        def after_func():
            """Return time after sunset."""
            return sun.next_setting(hass) + after_offset

    def time_if():
        """Validate time based if-condition."""
        now = dt_util.now()
        before = before_func()
        after = after_func()

        if before is not None and now > now.replace(hour=before.hour,
                                                    minute=before.minute):
            return False

        if after is not None and now < now.replace(hour=after.hour,
                                                   minute=after.minute):
            return False

        return True

    return time_if


def _parse_offset(raw_offset):
    """Parse the offset."""
    if raw_offset is None:
        return timedelta(0)

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

    return offset
