"""
Offer LiteJet switch based automation rules.
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_PLATFORM, CONF_ENTITY_ID
import homeassistant.helpers.config_validation as cv
import homeassistant.components.litejet as litejet

DEPENDENCIES = ['litejet']

_LOGGER = logging.getLogger(__name__)

CONF_FOR = 'for'
CONF_NUMBER = 'number'

ATTR_NUMBER = 'number'

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'litejet',
    vol.Required(CONF_NUMBER): vol.Coerce(int),
    #vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_FOR, default=timedelta(0)): cv.time_period,
})


def async_trigger(hass, config, action):
    """Listen for events based on configuration."""
    #entity_id = config.get(CONF_ENTITY_ID)
    #entity = hass.states.get(entity_id)
    #number = entity.attributes[ATTR_NUMBER]
    number = config.get(CONF_NUMBER)
    for_time = config.get(CONF_FOR)

    @callback
    def call_action():
        """Call action with right context."""
        hass.async_run_job(action, {
            'trigger': {
                'platform': 'litejet',
                #'entity_id': entity_id,
                'number': number,
                'for': for_time
            },
        })

    litejet.CONNECTION.on_switch_released(number, call_action)
