"""
Offer sun based automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#sun-trigger
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
import homeassistant.util.dt as dt_util
from homeassistant.components import sun
from homeassistant.helpers.event import track_sunrise, track_sunset
import homeassistant.helpers.config_validation as cv

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


_SUN_EVENT = vol.All(vol.Lower, vol.Any(EVENT_SUNRISE, EVENT_SUNSET))

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'sun',
    vol.Required(CONF_EVENT): _SUN_EVENT,
    vol.Required(CONF_OFFSET, default=timedelta(0)): cv.time_offset,
})

IF_ACTION_SCHEMA = vol.All(
    vol.Schema({
        vol.Required(CONF_PLATFORM): 'sun',
        CONF_BEFORE: _SUN_EVENT,
        CONF_AFTER: _SUN_EVENT,
        vol.Required(CONF_BEFORE_OFFSET, default=timedelta(0)): cv.time_offset,
        vol.Required(CONF_AFTER_OFFSET, default=timedelta(0)): cv.time_offset,
    }),
    cv.has_at_least_one_key(CONF_BEFORE, CONF_AFTER),
)


def trigger(hass, config, action):
    """Listen for events based on configuration."""
    event = config.get(CONF_EVENT)
    offset = config.get(CONF_OFFSET)

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
    before_offset = config.get(CONF_BEFORE_OFFSET)
    after_offset = config.get(CONF_AFTER_OFFSET)

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
