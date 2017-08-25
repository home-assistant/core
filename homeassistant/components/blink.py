"""
Support for Blink Home Camera System.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/blink/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, ATTR_FRIENDLY_NAME, ATTR_ARMED)
from homeassistant.helpers import discovery

REQUIREMENTS = ['blinkpy==0.6.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'blink'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

ARM_SYSTEM_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ARMED): cv.boolean
})

ARM_CAMERA_SCHEMA = vol.Schema({
    vol.Required(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(ATTR_ARMED): cv.boolean
})

SNAP_PICTURE_SCHEMA = vol.Schema({
    vol.Required(ATTR_FRIENDLY_NAME): cv.string
})


class BlinkSystem(object):
    """Blink System class."""

    def __init__(self, config_info):
        """Initialize the system."""
        import blinkpy
        self.blink = blinkpy.Blink(username=config_info[DOMAIN][CONF_USERNAME],
                                   password=config_info[DOMAIN][CONF_PASSWORD])
        self.blink.setup_system()


def setup(hass, config):
    """Set up Blink System."""
    hass.data[DOMAIN] = BlinkSystem(config)
    discovery.load_platform(hass, 'camera', DOMAIN, {}, config)
    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, {}, config)

    def snap_picture(call):
        """Take a picture."""
        cameras = hass.data[DOMAIN].blink.cameras
        name = call.data.get(ATTR_FRIENDLY_NAME, '')
        if name in cameras:
            cameras[name].snap_picture()

    def arm_camera(call):
        """Arm a camera."""
        cameras = hass.data[DOMAIN].blink.cameras
        name = call.data.get(ATTR_FRIENDLY_NAME, '')
        value = call.data.get(ATTR_ARMED, True)
        if name in cameras:
            cameras[name].set_motion_detect(value)

    def arm_system(call):
        """Arm the system."""
        value = call.data.get(ATTR_ARMED, True)
        hass.data[DOMAIN].blink.arm = value
        hass.data[DOMAIN].blink.refresh()

    hass.services.register(
        DOMAIN, 'snap_picture', snap_picture, schema=SNAP_PICTURE_SCHEMA)
    hass.services.register(
        DOMAIN, 'arm_camera', arm_camera, schema=ARM_CAMERA_SCHEMA)
    hass.services.register(
        DOMAIN, 'arm_system', arm_system, schema=ARM_SYSTEM_SCHEMA)

    return True
