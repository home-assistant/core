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

DEPENDENCIES = ['litejet']

_LOGGER = logging.getLogger(__name__)

CONF_NUMBER = 'number'

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'litejet',
    vol.Required(CONF_NUMBER): cv.positive_int
})


def async_trigger(hass, config, action):
    """Listen for events based on configuration."""
    number = config.get(CONF_NUMBER)

    @callback
    def call_action():
        """Call action with right context."""
        hass.async_run_job(action, {
            'trigger': {
                CONF_PLATFORM: 'litejet',
                CONF_NUMBER: number
            },
        })

    hass.data['litejet_system'].on_switch_released(number, call_action)
