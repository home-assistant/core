"""
Trigger an automation when a LiteJet switch is released.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/automation.litejet/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_PLATFORM
import homeassistant.helpers.config_validation as cv
import homeassistant.components.litejet as litejet

DEPENDENCIES = ['litejet']

_LOGGER = logging.getLogger(__name__)

CONF_NUMBER = 'number'

ATTR_NUMBER = 'number'

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'litejet',
    vol.Required(CONF_NUMBER): vol.Coerce(int)
})


def async_trigger(hass, config, action):
    """Listen for events based on configuration."""
    number = config.get(CONF_NUMBER)

    @callback
    def call_action():
        """Call action with right context."""
        hass.async_run_job(action, {
            'trigger': {
                'platform': 'litejet',
                'number': number
            },
        })

    litejet.CONNECTION.on_switch_released(number, call_action)
