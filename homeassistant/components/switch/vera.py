"""
Support for Vera switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.vera/
"""
import logging

from homeassistant.util import convert
from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchDevice
from homeassistant.components.vera import (
    VERA_CONTROLLER, VERA_DEVICES, VeraDevice)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Vera switches."""
    add_entities(
        [VeraSwitch(device, hass.data[VERA_CONTROLLER]) for
         device in hass.data[VERA_DEVICES]['switch']], True)


class VeraSwitch(VeraDevice, SwitchDevice):
    """Representation of a Vera Switch."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        self._state = False
        VeraDevice.__init__(self, vera_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.vera_device.switch_on()
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.vera_device.switch_off()
        self._state = False
        self.schedule_update_ha_state()

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        power = self.vera_device.power
        if power:
            return convert(power, float, 0.0)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Update device state."""
        self._state = self.vera_device.is_switched_on()
