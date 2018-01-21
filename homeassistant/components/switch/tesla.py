"""
Support for Tesla charger switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tesla/
"""
import logging

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchDevice
from homeassistant.components.tesla import DOMAIN as TESLA_DOMAIN
from homeassistant.components.tesla import TeslaDevice
from homeassistant.const import STATE_OFF, STATE_ON

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['tesla']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tesla switch platform."""
    devices = [ChargerSwitch(device, hass.data[TESLA_DOMAIN]['controller'])
               for device in hass.data[TESLA_DOMAIN]['devices']['switch']]
    add_devices(devices, True)


class ChargerSwitch(TeslaDevice, SwitchDevice):
    """Representation of a Tesla charger switch."""

    def __init__(self, tesla_device, controller):
        """Initialise of the switch."""
        self._state = None
        super().__init__(tesla_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.tesla_id)

    def turn_on(self, **kwargs):
        """Send the on command."""
        _LOGGER.debug("Enable charging: %s", self._name)
        self.tesla_device.start_charge()

    def turn_off(self, **kwargs):
        """Send the off command."""
        _LOGGER.debug("Disable charging  for: %s", self._name)
        self.tesla_device.stop_charge()

    @property
    def is_on(self):
        """Get whether the switch is in on state."""
        return self._state == STATE_ON

    def update(self):
        """Update the state of the switch."""
        _LOGGER.debug("Updating state for: %s", self._name)
        self.tesla_device.update()
        self._state = STATE_ON if self.tesla_device.is_charging() \
            else STATE_OFF
