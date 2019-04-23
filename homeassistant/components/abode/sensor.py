"""Support for Abode Security System sensors."""
import logging

from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE)

from . import DOMAIN as ABODE_DOMAIN, AbodeDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['abode']

# Sensor types: Name, icon
SENSOR_TYPES = {
    'temp': ['Temperature', DEVICE_CLASS_TEMPERATURE],
    'humidity': ['Humidity', DEVICE_CLASS_HUMIDITY],
    'lux': ['Lux', DEVICE_CLASS_ILLUMINANCE],
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for an Abode device."""
    import abodepy.helpers.constants as CONST

    data = hass.data[ABODE_DOMAIN]

    devices = []
    for device in data.abode.get_devices(generic_type=CONST.TYPE_SENSOR):
        if data.is_excluded(device):
            continue

        for sensor_type in SENSOR_TYPES:
            devices.append(AbodeSensor(data, device, sensor_type))

    data.devices.extend(devices)

    add_entities(devices)


class AbodeSensor(AbodeDevice):
    """A sensor implementation for Abode devices."""

    def __init__(self, data, device, sensor_type):
        """Initialize a sensor for an Abode device."""
        super().__init__(data, device)
        self._sensor_type = sensor_type
        self._name = '{0} {1}'.format(
            self._device.name, SENSOR_TYPES[self._sensor_type][0])
        self._device_class = SENSOR_TYPES[self._sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensor_type == 'temp':
            return self._device.temp
        if self._sensor_type == 'humidity':
            return self._device.humidity
        if self._sensor_type == 'lux':
            return self._device.lux

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        if self._sensor_type == 'temp':
            return self._device.temp_unit
        if self._sensor_type == 'humidity':
            return self._device.humidity_unit
        if self._sensor_type == 'lux':
            return self._device.lux_unit
