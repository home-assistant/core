"""Support for Ecobee binary sensors."""
from homeassistant.components import ecobee
from homeassistant.components.binary_sensor import BinarySensorDevice

ECOBEE_CONFIG_FILE = 'ecobee.conf'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ecobee sensors."""
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

    add_entities(dev, True)


class EcobeeBinarySensor(BinarySensorDevice):
    """Representation of an Ecobee sensor."""

    def __init__(self, sensor_name, sensor_index):
        """Initialize the Ecobee sensor."""
        self._name = sensor_name + ' Occupancy'
        self.sensor_name = sensor_name
        self.index = sensor_index
        self._state = None
        self._device_class = 'occupancy'

    @property
    def name(self):
        """Return the name of the Ecobee sensor."""
        return self._name.rstrip()

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state == 'true'

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._device_class

    def update(self):
        """Get the latest state of the sensor."""
        data = ecobee.NETWORK
        data.update()
        for sensor in data.ecobee.get_remote_sensors(self.index):
            for item in sensor['capability']:
                if (item['type'] == 'occupancy' and
                        self.sensor_name == sensor['name']):
                    self._state = item['value']
