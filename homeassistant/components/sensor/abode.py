"""
Support for Abode Security System sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.abode/
"""
import logging

from homeassistant.components.abode import AbodeDevice, DOMAIN as ABODE_DOMAIN

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['abode']

# Sensor types: Name, icon
SENSOR_TYPES = {
    'temp': ['Temperature', 'thermometer'],
    'humidity': ['Humidity', 'water-percent'],
    'lux': ['Lux', 'lightbulb'],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
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

    add_devices(devices)


class AbodeSensor(AbodeDevice):
    """A sensor implementation for Abode devices."""

    def __init__(self, data, device, sensor_type):
        """Initialize a sensor for an Abode device."""
        super().__init__(data, device)
        self._sensor_type = sensor_type
        self._icon = 'mdi:{}'.format(SENSOR_TYPES[self._sensor_type][1])
        self._name = '{0} {1}'.format(self._device.name,
                                      SENSOR_TYPES[self._sensor_type][0])

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensor_type == 'temp':
            return self._device.temp
        elif self._sensor_type == 'humidity':
            return self._device.humidity
        elif self._sensor_type == 'lux':
            return self._device.lux

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        if self._sensor_type == 'temp':
            return self._device.temp_unit
        elif self._sensor_type == 'humidity':
            return self._device.humidity_unit
        elif self._sensor_type == 'lux':
            return self._device.lux_unit
