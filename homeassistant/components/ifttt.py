"""
Support to trigger Maker IFTTT recipes.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ifttt/
"""
import logging

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyfttt==0.3']

_LOGGER = logging.getLogger(__name__)

ATTR_EVENT = 'event'
ATTR_VALUE1 = 'value1'
ATTR_VALUE2 = 'value2'
ATTR_VALUE3 = 'value3'

CONF_KEY = 'key'

DOMAIN = 'ifttt'

SERVICE_TRIGGER = 'trigger'

SERVICE_TRIGGER_SCHEMA = vol.Schema({
    vol.Required(ATTR_EVENT): cv.string,
    vol.Optional(ATTR_VALUE1): cv.string,
    vol.Optional(ATTR_VALUE2): cv.string,
    vol.Optional(ATTR_VALUE3): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_KEY): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def trigger(hass, event, value1=None, value2=None, value3=None):
    """Trigger a Maker IFTTT recipe."""
    data = {
        ATTR_EVENT: event,
        ATTR_VALUE1: value1,
        ATTR_VALUE2: value2,
        ATTR_VALUE3: value3,
    }
    hass.services.call(DOMAIN, SERVICE_TRIGGER, data)


def setup(hass, config):
    """Set up the IFTTT service component."""
    key = config[DOMAIN][CONF_KEY]

    def trigger_service(call):
        """Handle IFTTT trigger service calls."""
        event = call.data[ATTR_EVENT]
        value1 = call.data.get(ATTR_VALUE1)
        value2 = call.data.get(ATTR_VALUE2)
        value3 = call.data.get(ATTR_VALUE3)

        try:
            import pyfttt as pyfttt
            pyfttt.send_event(key, event, value1, value2, value3)
        except requests.exceptions.RequestException:
            _LOGGER.exception("Error communicating with IFTTT")

    hass.services.register(DOMAIN, SERVICE_TRIGGER, trigger_service,
                           schema=SERVICE_TRIGGER_SCHEMA)

    return True
