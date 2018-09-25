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
    CONF_USERNAME, CONF_PASSWORD, CONF_NAME)
from homeassistant.util import Throttle

REQUIREMENTS = ['blinkpy==0.8.3']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'blink'
DEFAULT_BRAND = 'blink'
DEFAULT_ATTRIBUTION = "Data provided by immedia-semi.com"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_TRIGGER = 'trigger_camera'
SERVICE_TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string
})


class BlinkSystem:
    """Blink System class."""

    def __init__(self, config_info):
        """Initialize the system."""
        import blinkpy.blinkpy as blink
        self.blink = blink.Blink(username=config_info[DOMAIN][CONF_USERNAME],
                                 password=config_info[DOMAIN][CONF_PASSWORD])
        self.blink.start()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def refresh(self):
        """Refresh the blink cameras."""
        self.blink.refresh()


def setup(hass, config):
    """Set up Blink System."""
    hass.data[DOMAIN] = BlinkSystem(config)

    def trigger_camera(call):
        """Trigger a camera."""
        cameras = hass.data[DOMAIN].blink.cameras
        name = call.data.get(CONF_NAME, '')
        if name in cameras:
            cameras[name].snap_picture()
        hass.data[DOMAIN].blink.refresh()

    hass.services.register(
        DOMAIN, SERVICE_TRIGGER, trigger_camera, schema=SERVICE_TRIGGER_SCHEMA
    )
    return True
