"""Offer time listening automation rules."""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_AT, CONF_PLATFORM
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'time',
    vol.Required(CONF_AT): cv.time,
})


async def async_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    at_time = config.get(CONF_AT)
    hours, minutes, seconds = at_time.hour, at_time.minute, at_time.second

    @callback
    def time_automation_listener(now):
        """Listen for time changes and calls action."""
        hass.async_run_job(action, {
            'trigger': {
                'platform': 'time',
                'now': now,
            },
        })

    return async_track_time_change(hass, time_automation_listener,
                                   hour=hours, minute=minutes, second=seconds)
