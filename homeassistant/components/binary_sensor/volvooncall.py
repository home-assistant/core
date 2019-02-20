"""
Support for VOC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.volvooncall/
"""
import logging

from homeassistant.components.volvooncall import VolvoEntity, DATA_KEY
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, DEVICE_CLASSES)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Volvo sensors."""
    if discovery_info is None:
        return
    async_add_entities([VolvoSensor(hass.data[DATA_KEY], *discovery_info)])


class VolvoSensor(VolvoEntity, BinarySensorDevice):
    """Representation of a Volvo sensor."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self.instrument.is_on

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        if self.instrument.device_class in DEVICE_CLASSES:
            return self.instrument.device_class
        return None
