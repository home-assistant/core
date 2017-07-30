"""
Support for X10 lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.x10/
"""
import logging
from subprocess import check_output, CalledProcessError, STDOUT

import voluptuous as vol

from homeassistant.const import (CONF_NAME, CONF_ID, CONF_DEVICES)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SUPPORT_X10 = SUPPORT_BRIGHTNESS

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [
        {
            vol.Required(CONF_ID): cv.string,
            vol.Required(CONF_NAME): cv.string,
        }
    ]),
})


def x10_command(command):
    """Execute X10 command and check output."""
    return check_output(['heyu'] + command.split(' '), stderr=STDOUT)


def get_unit_status(code):
    """Get on/off status for given unit."""
    output = check_output('heyu onstate ' + code, shell=True)
    return int(output.decode('utf-8')[0])


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the x10 Light platform."""
    try:
        x10_command('info')
    except CalledProcessError as err:
        _LOGGER.error(err.output)
        return False

    add_devices(X10Light(light) for light in config[CONF_DEVICES])


class X10Light(Light):
    """Representation of an X10 Light."""

    def __init__(self, light):
        """Initialize an X10 Light."""
        self._name = light['name']
        self._id = light['id']
        self._brightness = 0
        self._state = False

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_X10

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        x10_command('on ' + self._id)
        self._brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._state = True

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        x10_command('off ' + self._id)
        self._state = False

    def update(self):
        """Fetch update state."""
        self._state = bool(get_unit_status(self._id))
