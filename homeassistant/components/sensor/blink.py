"""
Support for Blink system camera sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.blink/
"""
import logging

from homeassistant.components.blink import DOMAIN
from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['blink']

SENSOR_TYPES = {
    'temperature': ['Temperature', TEMP_FAHRENHEIT],
    'battery': ['Battery', ''],
    'notifications': ['Notifications', '']
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a Blink sensor."""
    if discovery_info is None:
        return

    data = hass.data[DOMAIN].blink
    devs = list()
    index = 0
    for name in data.cameras:
        devs.append(BlinkSensor(name, 'temperature', index, data))
        devs.append(BlinkSensor(name, 'battery', index, data))
        devs.append(BlinkSensor(name, 'notifications', index, data))
        index += 1

    add_devices(devs, True)


class BlinkSensor(Entity):
    """A Blink camera sensor."""

    def __init__(self, name, sensor_type, index, data):
        """Initialize sensors from Blink camera."""
        self._name = 'blink_' + name + '_' + SENSOR_TYPES[sensor_type][0]
        self._camera_name = name
        self._type = sensor_type
        self.data = data
        self.index = index
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the camera."""
        return self._name

    @property
    def state(self):
        """Return the camera's current state."""
        return self._state

    @property
    def unique_id(self):
        """Return the unique camera sensor identifier."""
        return "sensor_{}_{}".format(self._name, self.index)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Retrieve sensor data from the camera."""
        camera = self.data.cameras[self._camera_name]
        if self._type == 'temperature':
            self._state = camera.temperature
        elif self._type == 'battery':
            self._state = camera.battery_string
        elif self._type == 'notifications':
            self._state = camera.notifications
        else:
            self._state = None
            _LOGGER.warning("Could not retrieve state from %s", self.name)
