"""
Support KNX switching actuators.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.knx/

(c) 2016 Daniel Matuschek <info@open-homeautomation.com>
"""
from homeassistant.components.switch import SwitchDevice
from homeassistant.components.knx import (
    KNXConfig, KNXGroupAddress)

DEPENDENCIES = ["knx"]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create and add an entity based on the configuration."""
    add_entities([
        KNXSwitch(hass, KNXConfig(config))
    ])


class KNXSwitch(KNXGroupAddress, SwitchDevice):
    """Representation of a KNX switch device."""

    def turn_on(self, **kwargs):
        """Turn the switch on.

        This sends a value 0 to the group address of the device
        """
        self.group_write(1)
        self._state = [1]
        if self.should_poll == False:
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off.

        This sends a value 1 to the group address of the device
        """
        self.group_write(0)
        self._state = [0]
        if self.should_poll == False:
            self.update_ha_state()
