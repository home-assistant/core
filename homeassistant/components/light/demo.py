""" Provides demo lights. """
import random

from homeassistant.helpers.device import ToggleDevice
from homeassistant.const import STATE_ON, STATE_OFF, DEVICE_DEFAULT_NAME
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_XY_COLOR


LIGHT_COLORS = [
    [0.861, 0.3259],
    [0.6389, 0.3028],
    [0.1684, 0.0416]
]


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return demo lights. """
    add_devices_callback([
        DemoLight("Bed Light", STATE_OFF),
        DemoLight("Ceiling", STATE_ON),
        DemoLight("Kitchen", STATE_ON)
    ])


class DemoLight(ToggleDevice):
    """ Provides a demo switch. """
    def __init__(self, name, state, xy=None, brightness=180):
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self._xy = xy or random.choice(LIGHT_COLORS)
        self._brightness = brightness

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def state(self):
        """ Returns the name of the device if any. """
        return self._state

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        if self.is_on:
            return {
                ATTR_BRIGHTNESS: self._brightness,
                ATTR_XY_COLOR: self._xy,
            }

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self._state = STATE_ON

        if ATTR_XY_COLOR in kwargs:
            self._xy = kwargs[ATTR_XY_COLOR]

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self._state = STATE_OFF
