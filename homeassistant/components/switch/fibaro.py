"""
Support for Fibaro switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.fibaro/
"""
import logging

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchDevice
from homeassistant.components.fibaro import (
    FIBARO_CONTROLLER, FIBARO_DEVICES, FibaroDevice)

DEPENDENCIES = ['fibaro']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Fibaro switches."""
    add_entities(
        [FibaroSwitch(device, hass.data[FIBARO_CONTROLLER]) for
         device in hass.data[FIBARO_DEVICES]['switch']], True)


class FibaroSwitch(FibaroDevice, SwitchDevice):
    """Representation of a Fibaro Switch."""

    def __init__(self, fibaro_device, controller):
        """Initialize the Fibaro device."""
        self._state = False
        FibaroDevice.__init__(self, fibaro_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.switch_on()
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.switch_off()
        self._state = False
        self.schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Update device state."""
        self._state = self.current_binary_state
