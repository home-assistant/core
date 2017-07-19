"""
Support for Tahoma cover - rollershutters etc.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.tahoma/
"""
import logging

from homeassistant.components.cover import CoverDevice, ENTITY_ID_FORMAT
from homeassistant.components.tahoma import (TAHOMA_DEVICES, TahomaDevice)
from homeassistant.components.tahoma_api import (Action)

DEPENDENCIES = ['tahoma']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tahoma covers."""
    add_devices(
        TahomaCover(device, TAHOMA_DEVICES['api']) for
        device in TAHOMA_DEVICES['cover'])


class TahomaCover(TahomaDevice, CoverDevice):
    """Representation a Tahoma Cover."""

    def __init__(self, tahoma_device, controller):
        """Initialize the Tahoma device."""
        TahomaDevice.__init__(self, tahoma_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.tahoma_id)

    def update(self):
        """update method."""
        self.controller.getStates([self.tahoma_device])
        self.schedule_update_ha_state()

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        0 is closed, 100 is fully open.
        """
        position = 100 - self.tahoma_device.activeStates['core:ClosureState']
        if position <= 5:
            return 0
        if position >= 95:
            return 100
        return position

    def set_cover_position(self, position, **kwargs):
        """Move the cover to a specific position."""
        a = Action(self.tahoma_device.url)
        a.addCommand('setPosition', 100 - position)
        self.controller.applyActions("", [a])
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
        a = Action(self.tahoma_device.url)
        a.addCommand('open')
        self.controller.applyActions('', [a])
        self.schedule_update_ha_state()

    def close_cover(self, **kwargs):
        """Close the cover."""
        a = Action(self.tahoma_device.url)
        a.addCommand('close')
        self.controller.applyActions('', [a])
        self.schedule_update_ha_state()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        a = Action(self.tahoma_device.url)
        a.addCommand('stopIdentify')
        self.controller.applyActions('', [a])
        self.schedule_update_ha_state()
