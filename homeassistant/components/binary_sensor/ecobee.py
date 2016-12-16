"""
Support for Ecobee sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.ecobee/
"""
from homeassistant.components import ecobee
from homeassistant.components.binary_sensor import BinarySensorDevice

DEPENDENCIES = ['ecobee']

ECOBEE_CONFIG_FILE = 'ecobee.conf'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Ecobee sensors."""
    if discovery_info is None:
        return
    data = ecobee.NETWORK
    dev = list()
    for index in range(len(data.ecobee.thermostats)):
        for sensor in data.ecobee.get_remote_sensors(index):
            for item in sensor['capability']:
                if item['type'] != 'occupancy':
                    continue

                dev.append(EcobeeBinarySensor(sensor['name'], index))

    add_devices(dev)


class EcobeeBinarySensor(BinarySensorDevice):
    """Representation of an Ecobee sensor."""

    def __init__(self, sensor_name, sensor_index):
        """Initialize the sensor."""
        self._name = sensor_name + ' Occupancy'
        self.sensor_name = sensor_name
        self.index = sensor_index
        self._state = None
        self._sensor_class = 'occupancy'
        self.update()

    @property
    def name(self):
        """Return the name of the Ecobee sensor."""
        return self._name.rstrip()

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state == 'true'

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return "binary_sensor_ecobee_{}_{}".format(self._name, self.index)

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return self._sensor_class

    def update(self):
        """Get the latest state of the sensor."""
        data = ecobee.NETWORK
        data.update()
        for sensor in data.ecobee.get_remote_sensors(self.index):
            for item in sensor['capability']:
                if (item['type'] == 'occupancy' and
                        self.sensor_name == sensor['name']):
                    self._state = item['value']
