"""
Support for Harmony device current activity as a sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/harmony/
"""

import logging
import homeassistant.components.harmony as harmony

DEPENDENCIES = ['harmony']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""

    for hub in harmony.HARMONY:
        add_devices([HarmonySensor(harmony.HARMONY[hub]['device'])])
    return True



class HarmonySensor(harmony.HarmonyDevice):
    """Representation of a Harmony Sensor."""
    def __init__(self, harmony_device):
        self._harmony_device = harmony_device
        self._name = 'harmony_' + self._harmony_device.name

    @property
    def state(self):
        """Return the state of the Harmony device."""
        return self.get_status()


    def get_status(self):
        return str(self._harmony_device.state)



   





