"""
Support for Fibaro switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.fibaro/
"""
import logging

from homeassistant.util import convert
from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchDevice
from homeassistant.components.fibaro import (
    FIBARO_CONTROLLER, FIBARO_DEVICES, FibaroDevice)

DEPENDENCIES = ['fibaro']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Fibaro switches."""
    if discovery_info is None:
        return

    add_entities(
        [FibaroSwitch(device, hass.data[FIBARO_CONTROLLER]) for
         device in hass.data[FIBARO_DEVICES]['switch']], True)


class FibaroSwitch(FibaroDevice, SwitchDevice):
    """Representation of a Fibaro Switch."""

    def __init__(self, fibaro_device, controller):
        """Initialize the Fibaro device."""
        self._state = False
        super().__init__(fibaro_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.call_turn_on()
        self._state = True

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.call_turn_off()
        self._state = False

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        if 'power' in self.fibaro_device.interfaces:
            return convert(self.fibaro_device.properties.power, float, 0.0)
        return None

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        if 'energy' in self.fibaro_device.interfaces:
            return convert(self.fibaro_device.properties.energy, float, 0.0)
        return None

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Update device state."""
        self._state = self.current_binary_state
