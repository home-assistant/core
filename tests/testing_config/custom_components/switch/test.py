"""
Provide a mock switch platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.const import STATE_ON, STATE_OFF
from tests.common import MockToggleDevice


DEVICES = []


def init(empty=False):
    """Initialize the platform with devices."""
    global DEVICES

    DEVICES = [] if empty else [
        MockToggleDevice('AC', STATE_ON),
        MockToggleDevice('AC', STATE_OFF),
        MockToggleDevice(None, STATE_OFF)
    ]


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Find and return test switches."""
    add_devices_callback(DEVICES)
