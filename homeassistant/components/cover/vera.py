"""
Support for Vera cover - curtains, rollershutters etc.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.vera/
"""
import logging

from homeassistant.components.cover import CoverDevice
from homeassistant.components.vera import (
    VeraDevice, VERA_DEVICES, VERA_CONTROLLER)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Find and return Vera covers."""
    add_devices_callback(
        VeraCover(device, VERA_CONTROLLER) for
        device in VERA_DEVICES['cover'])


# pylint: disable=abstract-method
class VeraCover(VeraDevice, CoverDevice):
    """Represents a Vera Cover in Home Assistant."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        VeraDevice.__init__(self, vera_device, controller)

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        0 is closed, 100 is fully open.
        """
        position = self.vera_device.get_level()
        if position <= 5:
            return 0
        if position >= 95:
            return 100
        return position

    def set_cover_position(self, position, **kwargs):
        """Move the cover to a specific position."""
        self.vera_device.set_level(position)

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self.current_cover_position is not None:
            if self.current_cover_position > 0:
                return False
            else:
                return True

    def open_cover(self, **kwargs):
        """Open the cover."""
        self.vera_device.open()

    def close_cover(self, **kwargs):
        """Close the cover."""
        self.vera_device.close()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.vera_device.stop()
