"""
Support for Ecobee sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ecobee/
"""
from homeassistant.components import ecobee
from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.util.temperature import calculate_dewpoint
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['ecobee']

ECOBEE_CONFIG_FILE = 'ecobee.conf'

SENSOR_TYPES = {
    'temperature': ['Temperature', TEMP_FAHRENHEIT],
    'humidity': ['Humidity', '%'],
    'dewpoint': ['Dewpoint', TEMP_FAHRENHEIT],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
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
            dev.append(EcobeeSensor(sensor['name'], 'dewpoint', index))

    add_devices(dev, True)


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
        return self._name.rstrip()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return "sensor_ecobee_{}_{}".format(self._name, self.index)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest state of the sensor."""
        data = ecobee.NETWORK
        data.update()
        for sensor in data.ecobee.get_remote_sensors(self.index):
            if self.sensor_name != sensor['name']:
                continue
            values = {c['type']: c['value'] for c in sensor['capability']}
            if self.type in values:
                if self.type == 'temperature':
                    try:
                        self._state = float(values[self.type]) / 10
                    except (KeyError, ValueError):
                        continue
                else:
                    self._state = values[self.type]
            elif self.type == 'dewpoint':
                try:
                    temperature = float(values['temperature']) / 10
                    humidity = float(values['humidity'])
                except (KeyError, ValueError):
                    continue
                self._state = round(
                    calculate_dewpoint(temperature, humidity,
                                       self.unit_of_measurement), 1)
