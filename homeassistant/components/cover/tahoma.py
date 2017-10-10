"""
Support for Tahoma cover - shutters etc.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.tahoma/
"""
import logging

from homeassistant.components.cover import CoverDevice, ENTITY_ID_FORMAT
from homeassistant.components.tahoma import (TahomaDevice)

DEPENDENCIES = ['tahoma']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tahoma covers."""
    add_devices(
        TahomaCover(device, hass.data['TAHOMA_CONTROLLER']) for
        device in hass.data['tahomacover'])


class TahomaCover(TahomaDevice, CoverDevice):
    """Representation a Tahoma Cover."""

    def __init__(self, tahoma_device, controller):
        """Initialize the Tahoma device."""
        TahomaDevice.__init__(self, tahoma_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.tahoma_id)

    def update(self):
        """Update method."""
        self.controller.get_states([self.tahoma_device])
        self.schedule_update_ha_state()

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        0 is closed, 100 is fully open.
        """
        position = 100 - self.tahoma_device.active_states['core:ClosureState']
        if position <= 5:
            return 0
        if position >= 95:
            return 100
        return position

    def set_cover_position(self, position, **kwargs):
        """Move the cover to a specific position."""
        self.apply_action('setPosition', 100 - position)
        self.schedule_update_ha_state()

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
        self.apply_action('open')
        self.schedule_update_ha_state()

    def close_cover(self, **kwargs):
        """Close the cover."""
        self.apply_action('close')
        self.schedule_update_ha_state()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.apply_action('stopIdentify')
        self.schedule_update_ha_state()
