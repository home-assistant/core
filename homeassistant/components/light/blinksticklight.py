"""
homeassistant.components.light.blinksticklight
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Blinkstick lights.
"""

from blinkstick import blinkstick
import logging

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.light import (Light, ATTR_RGB_COLOR)

REQUIREMENTS = ["blinkstick==1.1.7"]
DEPENDENCIES = []

# pylint: disable=unused-argument


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add device specified by serial number """
    stick = blinkstick.find_by_serial(config['serial'])

    add_devices_callback([BlinkStickLight(stick, config['name'])])


class BlinkStickLight(Light):
    """ Represents a BlinkStick light """

    def __init__(self, stick, name):
        """ Initialise """
        self._stick = stick
        self._name = name
        self._serial = stick.get_serial()
        self._rgb_color = stick.get_color()

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return self._name

    @property
    def rgb_color(self):
        """ Read back the color of the light """
        return self._rgb_color

    @property
    def is_on(self):
        """ Check whether any of the LEDs colors are non-zero """
        return sum(self._rgb_color) > 0

    def update(self):
        """ Read back the device state """
        self._rgb_color = self._stick.get_color()

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        if ATTR_RGB_COLOR in kwargs:
            self._rgb_color = kwargs[ATTR_RGB_COLOR]
        else:
            self._rgb_color = [255, 255, 255]

        self._stick.set_color(red=self._rgb_color[0],
                              green=self._rgb_color[1],
                              blue=self._rgb_color[2])

    def turn_off(self, **kwargs):
        """ Turn the device off """
        self._stick.turn_off()
