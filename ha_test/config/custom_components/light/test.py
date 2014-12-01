"""
custom_components.light.test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides a mock switch platform.

Call init before using it in your tests to ensure clean test data.
"""
import homeassistant.components as components
from ha_test.helper import MockToggleDevice


DEVICES = []


def init(empty=False):
    """ (re-)initalizes the platform with devices. """
    global DEVICES

    DEVICES = [] if empty else [
        MockToggleDevice('Ceiling', components.STATE_ON),
        MockToggleDevice('Ceiling', components.STATE_OFF),
        MockToggleDevice(None, components.STATE_OFF)
    ]


def get_lights(hass, config):
    """ Returns mock devices. """
    return DEVICES
