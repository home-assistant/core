"""
Trigger an automation when a LiteJet switch is released.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/automation.litejet/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_PLATFORM
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.helpers.event import track_point_in_utc_time

DEPENDENCIES = ['litejet']

_LOGGER = logging.getLogger(__name__)

CONF_NUMBER = 'number'
CONF_HELD_MORE_THAN = 'held_more_than'
CONF_HELD_LESS_THAN = 'held_less_than'

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'litejet',
    vol.Required(CONF_NUMBER): cv.positive_int,
    vol.Optional(CONF_HELD_MORE_THAN):
        vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_HELD_LESS_THAN):
        vol.All(cv.time_period, cv.positive_timedelta)
})


async def async_trigger(hass, config, action, automation_info):
    """Listen for events based on configuration."""
    number = config.get(CONF_NUMBER)
    held_more_than = config.get(CONF_HELD_MORE_THAN)
    held_less_than = config.get(CONF_HELD_LESS_THAN)
    pressed_time = None
    cancel_pressed_more_than = None

    @callback
    def call_action():
        """Call action with right context."""
        hass.async_run_job(action, {
            'trigger': {
                CONF_PLATFORM: 'litejet',
                CONF_NUMBER: number,
                CONF_HELD_MORE_THAN: held_more_than,
                CONF_HELD_LESS_THAN: held_less_than
            },
        })

    # held_more_than and held_less_than: trigger on released (if in time range)
    # held_more_than: trigger after pressed with calculation
    # held_less_than: trigger on released with calculation
    # neither: trigger on pressed

    @callback
    def pressed_more_than_satisfied(now):
        """Handle the LiteJet's switch's button pressed >= held_more_than."""
        call_action()

    def pressed():
        """Handle the press of the LiteJet switch's button."""
        nonlocal cancel_pressed_more_than, pressed_time
        nonlocal held_less_than, held_more_than
        pressed_time = dt_util.utcnow()
        if held_more_than is None and held_less_than is None:
            hass.add_job(call_action)
        if held_more_than is not None and held_less_than is None:
            cancel_pressed_more_than = track_point_in_utc_time(
                hass,
                pressed_more_than_satisfied,
                dt_util.utcnow() + held_more_than)

    def released():
        """Handle the release of the LiteJet switch's button."""
        nonlocal cancel_pressed_more_than, pressed_time
        nonlocal held_less_than, held_more_than
        # pylint: disable=not-callable
        if cancel_pressed_more_than is not None:
            cancel_pressed_more_than()
            cancel_pressed_more_than = None
        held_time = dt_util.utcnow() - pressed_time
        if held_less_than is not None and held_time < held_less_than:
            if held_more_than is None or held_time > held_more_than:
                hass.add_job(call_action)

    hass.data['litejet_system'].on_switch_pressed(number, pressed)
    hass.data['litejet_system'].on_switch_released(number, released)

    def async_remove():
        """Remove all subscriptions used for this trigger."""
        return

    return async_remove
