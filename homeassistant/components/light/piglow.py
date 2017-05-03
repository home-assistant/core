"""
Support for Piglow LED's.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.piglow/
"""
import logging
import subprocess

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, ATTR_RGB_COLOR, SUPPORT_RGB_COLOR,
    Light, PLATFORM_SCHEMA)
from homeassistant.const import CONF_NAME

REQUIREMENTS = ['piglow==1.2.4']

_LOGGER = logging.getLogger(__name__)

SUPPORT_PIGLOW = (SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR)

DEFAULT_NAME = 'Piglow'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Piglow Light platform."""
    import piglow

    if subprocess.getoutput("i2cdetect  -q -y 1 | grep -o 54") != '54':
        _LOGGER.error("A Piglow device was not found")
        return False

    name = config.get(CONF_NAME)

    add_devices([PiglowLight(piglow, name)])


class PiglowLight(Light):
    """Representation of an Piglow Light."""

    def __init__(self, piglow, name):
        """Initialize an PiglowLight."""
        self._piglow = piglow
        self._name = name
        self._is_on = False
        self._brightness = 255
        self._rgb_color = [255, 255, 255]

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def rgb_color(self):
        """Read back the color of the light."""
        return self._rgb_color

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_PIGLOW

    @property
    def should_poll(self):
        """Return if we should poll this device."""
        return False

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return True

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        self._piglow.clear()

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        percent_bright = (self._brightness / 255)

        if ATTR_RGB_COLOR in kwargs:
            self._rgb_color = kwargs[ATTR_RGB_COLOR]
            self._piglow.red(int(self._rgb_color[0] * percent_bright))
            self._piglow.green(int(self._rgb_color[1] * percent_bright))
            self._piglow.blue(int(self._rgb_color[2] * percent_bright))
        else:
            self._piglow.all(self._brightness)
        self._piglow.show()
        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._piglow.clear()
        self._piglow.show()
        self._is_on = False
        self.schedule_update_ha_state()
