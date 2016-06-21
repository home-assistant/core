"""
The homematic switch platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.homematic/

Important: For this platform to work the homematic component has to be
properly configured.

Configuration:

switch:
  - platform: homematic
    address: "<Homematic address for device>" # e.g. "JEQ0XXXXXXX"
    name: "<User defined name>" (optional)
"""

import logging
from homeassistant.components.switch import SwitchDevice
import homeassistant.components.homematic as homematic

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the platform."""
    return homematic.setup_hmdevice_entity_helper(HMSwitch,
                                                  config,
                                                  add_callback_devices)


class HMSwitch(homematic.HMDevice, SwitchDevice):
    """Represents an Homematic Switch in Home Assistant."""

    @property
    def is_on(self):
        """Return True if switch is on."""
        return bool(self._get_state())

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self._connected:
            self._hmdevice.on()
            self._set_state(True)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self._connected:
            self._hmdevice.off()
            self._set_state(False)
