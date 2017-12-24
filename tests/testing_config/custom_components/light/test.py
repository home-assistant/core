"""
Provide a mock light platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.const import STATE_ON, STATE_OFF
from tests.common import MockToggleDevice


DEVICES = []


def init(empty=False):
    """Initialize the platform with devices."""
    global DEVICES

    DEVICES = [] if empty else [
        MockLightDevice('Ceiling', STATE_ON),
        MockLightDevice('Ceiling', STATE_OFF),
        MockLightDevice(None, STATE_OFF)
    ]


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Return mock devices."""
    add_devices_callback(DEVICES)


class MockLightDevice(MockToggleDevice):
    """Provide a mock toggle device."""

    def __init__(self, name, state):
        """Initialize the mock device."""
        super().__init__(name, state)
        self._supported_features = 0
        self._state_attributes = {}

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def state_attributes(self):
        """Return optional state attributes."""
        return self._state_attributes
