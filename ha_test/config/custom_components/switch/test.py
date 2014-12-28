"""
custom_components.switch.test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides a mock switch platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.const import STATE_ON, STATE_OFF
from ha_test.helpers import MockToggleDevice


DEVICES = []


def init(empty=False):
    """ (re-)initalizes the platform with devices. """
    global DEVICES

    DEVICES = [] if empty else [
        MockToggleDevice('AC', STATE_ON),
        MockToggleDevice('AC', STATE_OFF),
        MockToggleDevice(None, STATE_OFF)
    ]


def get_switches(hass, config):
    """ Returns mock devices. """
    return DEVICES
