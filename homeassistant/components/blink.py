"""
Support for Blink Home Camera System.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/blink/
"""
from datetime import timedelta
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, ATTR_FRIENDLY_NAME, ATTR_ARMED)
from homeassistant.helpers import discovery
from homeassistant.util import Throttle

REQUIREMENTS = ['blinkpy==0.8.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'blink'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=45)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


class BlinkSystem:
    """Blink System class."""

    def __init__(self, config_info):
        """Initialize the system."""
        import blinkpy.blinkpy as blinkpy
        self.blink = blinkpy.Blink(username=config_info[DOMAIN][CONF_USERNAME],
                                   password=config_info[DOMAIN][CONF_PASSWORD])
        self.blink.start()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def refresh(self):
        """Refresh the blink cameras."""
        self.blink.refresh()


def setup(hass, config):
    """Set up Blink System."""
    hass.data[DOMAIN] = BlinkSystem(config)

    return True
