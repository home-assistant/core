"""Support for Ecobee sensors."""
from homeassistant.components import ecobee
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['ecobee']

ECOBEE_CONFIG_FILE = 'ecobee.conf'

SENSOR_TYPES = {
    'temperature': ['Temperature', TEMP_FAHRENHEIT],
    'humidity': ['Humidity', '%']
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ecobee sensors."""
    if discovery_info is None:
        return
    data = ecobee.NETWORK
    dev = list()
    for index in range(len(data.ecobee.thermostats)):
        for sensor in data.ecobee.get_remote_sensors(index):
            for item in sensor['capability']:
                if item['type'] not in ('temperature', 'humidity'):
                    continue

                dev.append(EcobeeSensor(sensor['name'], item['type'], index))

    add_entities(dev, True)


class EcobeeSensor(Entity):
    """Representation of an Ecobee sensor."""

    def __init__(self, sensor_name, sensor_type, sensor_index):
        """Initialize the sensor."""
        self._name = '{} {}'.format(sensor_name, SENSOR_TYPES[sensor_type][0])
        self.sensor_name = sensor_name
        self.type = sensor_type
        self.index = sensor_index
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the Ecobee sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self.type in (DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE):
            return self.type
        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest state of the sensor."""
        data = ecobee.NETWORK
        data.update()
        for sensor in data.ecobee.get_remote_sensors(self.index):
            for item in sensor['capability']:
                if (item['type'] == self.type and
                        self.sensor_name == sensor['name']):
                    if (self.type == 'temperature' and
                            item['value'] != 'unknown'):
                        self._state = float(item['value']) / 10
                    else:
                        self._state = item['value']
