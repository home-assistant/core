"""
Offer sun based automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/docs/automation/trigger/#sun-trigger
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (
    CONF_EVENT, CONF_OFFSET, CONF_PLATFORM, SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET, SUN_EVENT_ASTRONOMICAL_DAWN, SUN_EVENT_ASTRONOMICAL_DUSK,
    SUN_EVENT_CIVIL_DAWN, SUN_EVENT_CIVIL_DUSK, SUN_EVENT_NAUTICAL_DAWN)
from homeassistant.helpers.event import (
    async_track_sunrise, async_track_sunset, async_track_astronomical_dawn,
    async_track_astronomical_dusk, async_track_civil_dawn,
    async_track_civil_dusk, async_track_nautical_dawn,
    async_track_nautical_dusk,
    )
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'sun',
    vol.Required(CONF_EVENT): cv.sun_event,
    vol.Required(CONF_OFFSET, default=timedelta(0)): cv.time_period,
})


async def async_trigger(hass, config, action):
    """Listen for events based on configuration."""
    event = config.get(CONF_EVENT)
    offset = config.get(CONF_OFFSET)

    @callback
    def call_action():
        """Call action with right context."""
        hass.async_run_job(action, {
            'trigger': {
                'platform': 'sun',
                'event': event,
                'offset': offset,
            },
        })

    if event == SUN_EVENT_SUNRISE:
        return async_track_sunrise(hass, call_action, offset)
    if event == SUN_EVENT_SUNSET:
        return async_track_sunset(hass, call_action, offset)
    if event == SUN_EVENT_ASTRONOMICAL_DAWN:
        return async_track_astronomical_dawn(hass, call_action, offset)
    if event == SUN_EVENT_ASTRONOMICAL_DUSK:
        return async_track_astronomical_dusk(hass, call_action, offset)
    if event == SUN_EVENT_CIVIL_DAWN:
        return async_track_civil_dawn(hass, call_action, offset)
    if event == SUN_EVENT_CIVIL_DUSK:
        return async_track_civil_dusk(hass, call_action, offset)
    if event == SUN_EVENT_NAUTICAL_DAWN:
        return async_track_nautical_dawn(hass, call_action, offset)
    return async_track_nautical_dusk(hass, call_action, offset)
