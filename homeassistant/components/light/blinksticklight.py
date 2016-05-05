"""
Support for Blinkstick lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.blinksticklight/
"""
import logging

from homeassistant.components.light import ATTR_RGB_COLOR, Light

_LOGGER = logging.getLogger(__name__)


REQUIREMENTS = ["blinkstick==1.1.7"]


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Add device specified by serial number."""
    from blinkstick import blinkstick

    stick = blinkstick.find_by_serial(config['serial'])

    add_devices_callback([BlinkStickLight(stick, config['name'])])


class BlinkStickLight(Light):
    """Representation of a BlinkStick light."""

    def __init__(self, stick, name):
        """Initialize the light."""
        self._stick = stick
        self._name = name
        self._serial = stick.get_serial()
        self._rgb_color = stick.get_color()

    @property
    def should_poll(self):
        """Polling needed."""
        return True

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def rgb_color(self):
        """Read back the color of the light."""
        return self._rgb_color

    @property
    def is_on(self):
        """Check whether any of the LEDs colors are non-zero."""
        return sum(self._rgb_color) > 0

    def update(self):
        """Read back the device state."""
        self._rgb_color = self._stick.get_color()

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_RGB_COLOR in kwargs:
            self._rgb_color = kwargs[ATTR_RGB_COLOR]
        else:
            self._rgb_color = [255, 255, 255]

        self._stick.set_color(red=self._rgb_color[0],
                              green=self._rgb_color[1],
                              blue=self._rgb_color[2])

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._stick.turn_off()
