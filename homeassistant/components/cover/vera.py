"""
Support for Vera cover - curtains, rollershutters etc.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.vera/
"""
import logging

from homeassistant.components.cover import CoverDevice, ENTITY_ID_FORMAT, \
    ATTR_POSITION
from homeassistant.components.vera import (
    VERA_CONTROLLER, VERA_DEVICES, VeraDevice)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Vera covers."""
    add_devices(
        VeraCover(device, hass.data[VERA_CONTROLLER]) for
        device in hass.data[VERA_DEVICES]['cover'])


class VeraCover(VeraDevice, CoverDevice):
    """Representation a Vera Cover."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        VeraDevice.__init__(self, vera_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

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

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        self.vera_device.set_level(kwargs.get(ATTR_POSITION))
        self.schedule_update_ha_state()

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self.current_cover_position is not None:
            return self.current_cover_position == 0

    def open_cover(self, **kwargs):
        """Open the cover."""
        self.vera_device.open()
        self.schedule_update_ha_state()

    def close_cover(self, **kwargs):
        """Close the cover."""
        self.vera_device.close()
        self.schedule_update_ha_state()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.vera_device.stop()
        self.schedule_update_ha_state()
