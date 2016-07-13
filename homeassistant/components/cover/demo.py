"""
Demo cover platform that has two fake covers.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.cover import CoverDevice
from homeassistant.const import STATE_CLOSED, STATE_OPEN


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup demo cover platform."""
    add_devices_callback([
        DemoCover('Garage Door', STATE_CLOSED),
        DemoCover('Kitchen Window', STATE_OPEN)
    ])


class DemoCover(CoverDevice):
    """Provides a demo cover."""

    def __init__(self, name, state):
        """Initialize the cover."""
        self._name = name
        self._state = state

    @property
    def should_poll(self):
        """No polling needed for a demo cover."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_open(self):
        """Return true if cover is closed."""
        return self._state == STATE_OPEN

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        return self._state == STATE_CLOSED

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._state = STATE_OPEN
        self.update_ha_state()

    def close_cover(self, **kwargs):
        """Close the cover."""
        self._state = STATE_CLOSED
        self.update_ha_state()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._state = STATE_CLOSED
        self.update_ha_state()
