"""
Provide a mock switch platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.light import (SUPPORT_XY_COLOR)
from tests.common import MockToggleDevice


DEVICES = []


class MockLightDevice(MockToggleDevice):
    """Provide a mock light device."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_XY_COLOR

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return None


def init(empty=False):
    """Initalize the platform with devices."""
    global DEVICES

    DEVICES = [] if empty else [
        MockLightDevice('Ceiling', STATE_ON),
        MockLightDevice('Ceiling', STATE_OFF),
        MockLightDevice(None, STATE_OFF)
    ]


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Return mock devices."""
    add_devices_callback(DEVICES)
