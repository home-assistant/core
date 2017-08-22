"""
This component provides HA binary_sensor support for Abode Security System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.abode/
"""
import logging

from homeassistant.components.abode import (
    AbodeDevice, CONF_ATTRIBUTION, DATA_ABODE)
from homeassistant.components.binary_sensor import (BinarySensorDevice)

DEPENDENCIES = ['abode']

_LOGGER = logging.getLogger(__name__)

# Sensor types: Name, device_class
SENSOR_TYPES = {
    'Door Contact': 'opening',
    'Motion Camera': 'motion',
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for an Abode device."""
    data = hass.data.get(DATA_ABODE)

    sensors = []
    for sensor in data.devices:
        _LOGGER.debug('Sensor type %s', sensor.type)
        if sensor.type in ['Door Contact', 'Motion Camera']:
            sensors.append(AbodeBinarySensor(hass, data, sensor))

    _LOGGER.debug('Adding %d sensors', len(sensors))
    add_devices(sensors)


class AbodeBinarySensor(AbodeDevice, BinarySensorDevice):
    """A binary sensor implementation for Abode device."""

    def __init__(self, hass, data, device):
        """Initialize a sensor for Abode device."""
        AbodeDevice.__init__(self, hass, data, device)

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        if self._device.type == 'Door Contact':
            return self._device.status != 'Closed'
        elif self._device.type == 'Motion Camera':
            return self._device.get_value('motion_event') == '1'
