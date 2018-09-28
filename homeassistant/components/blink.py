"""
Support for Blink Home Camera System.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/blink/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_NAME, CONF_SCAN_INTERVAL)

REQUIREMENTS = ['blinkpy==0.9.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'blink'
DEFAULT_BRAND = 'blink'
DEFAULT_ATTRIBUTION = "Data provided by immedia-semi.com"
SIGNAL_UPDATE_BLINK = "blink_update"
SCAN_INTERVAL = 60

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.positive_int
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_TRIGGER = 'trigger_camera'
SERVICE_TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string
})


def setup(hass, config):
    """Set up Blink System."""
    from blinkpy import blinkpy
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    scan_interval = config[DOMAIN].get(CONF_SCAN_INTERVAL)
    hass.data[DOMAIN] = blinkpy.Blink(username=username,
                                      password=password)
    hass.data[DOMAIN].refresh_rate = scan_interval
    hass.data[DOMAIN].start()

    def trigger_camera(call):
        """Trigger a camera."""
        cameras = hass.data[DOMAIN].blink.sync.cameras
        name = call.data.get(CONF_NAME, '')
        if name in cameras:
            cameras[name].snap_picture()
        hass.data[DOMAIN].refresh()

    def blink_refresh(event_time):
        """Call blink to refresh info."""
        _LOGGER.info("Updating Blink component")
        hass.data[DOMAIN].refresh()

    hass.services.register(DOMAIN, 'update', blink_refresh)
    hass.services.register(
        DOMAIN, SERVICE_TRIGGER, trigger_camera, schema=SERVICE_TRIGGER_SCHEMA
    )
    return True
