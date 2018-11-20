"""
Support for VOC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.volvooncall/
"""
import logging

from homeassistant.components.volvooncall import VolvoEntity
from homeassistant.components.binary_sensor import BinarySensorDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Volvo sensors."""
    if discovery_info is None:
        return
    add_entities([VolvoSensor(hass, *discovery_info)])


class VolvoSensor(VolvoEntity, BinarySensorDevice):
    """Representation of a Volvo sensor."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        val = getattr(self.vehicle, self._attribute)
        if self._attribute == 'bulb_failures':
            return bool(val)
        if self._attribute in ['doors', 'windows']:
            return any([val[key] for key in val if 'Open' in key])
        return val != 'Normal'

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return 'safety'
