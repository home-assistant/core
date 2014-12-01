"""
custom_components.switch.test
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
        MockToggleDevice('AC', components.STATE_ON),
        MockToggleDevice('AC', components.STATE_OFF),
        MockToggleDevice(None, components.STATE_OFF)
    ]


def get_switches(hass, config):
    """ Returns mock devices. """
    return DEVICES
