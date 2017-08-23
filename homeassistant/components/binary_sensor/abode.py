"""
This component provides HA binary_sensor support for Abode Security System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.abode/
"""
import logging

from homeassistant.components.abode import (CONF_ATTRIBUTION, DATA_ABODE)
from homeassistant.const import (ATTR_ATTRIBUTION)
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


class AbodeBinarySensor(BinarySensorDevice):
    """A binary sensor implementation for Abode device."""

    def __init__(self, hass, data, device):
        """Initialize a sensor for Abode device."""
        super(AbodeBinarySensor, self).__init__()
        self._device = device

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{0} {1}".format(self._device.type, self._device.name)

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        if self._device.type == 'Door Contact':
            return self._device.status != 'Closed'
        elif self._device.type == 'Motion Camera':
            return self._device.get_value('motion_event') == '1'

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return SENSOR_TYPES.get(self._device.type)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        attrs['device_id'] = self._device.device_id
        attrs['battery_low'] = self._device.battery_low

        return attrs

    def update(self):
        """Update the device state."""
        self._device.refresh()
