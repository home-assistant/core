"""
Support for Ecobee sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ecobee/
"""
from homeassistant.components import ecobee
from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['ecobee']

ECOBEE_CONFIG_FILE = 'ecobee.conf'

SENSOR_TYPES = {
    'temperature': ['Temperature', TEMP_FAHRENHEIT],
    'humidity': ['Humidity', '%']
}

REMOTE_SENSOR = 1
WEATHER_SENSOR = 2


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

                dev.append(EcobeeSensor(sensor['name'], item['type'],
                                        index, REMOTE_SENSOR))
        thermostat = data.ecobee.get_thermostat(index)
        if 'weather' in thermostat and 'forecasts' in thermostat['weather']:
            forecasts = thermostat['weather']['forecasts']
            if forecasts:
                for sensor_type in ('temperature', 'humidity'):
                    dev.append(EcobeeSensor("Outside", sensor_type,
                                            index, WEATHER_SENSOR))

    add_devices(dev, True)


class EcobeeSensor(Entity):
    """Representation of an Ecobee sensor."""

    def __init__(self, sensor_name, sensor_type, sensor_index, sensor_class):
        """Initialize the sensor."""
        self._name = '{} {}'.format(sensor_name, SENSOR_TYPES[sensor_type][0])
        self.sensor_name = sensor_name
        self.type = sensor_type
        self.index = sensor_index
        self._class = sensor_class
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
        if self._class == WEATHER_SENSOR:
            thermostat = data.ecobee.get_thermostat(self.index)
            if ('weather' in thermostat and
                    'forecasts' in thermostat['weather']):
                forecasts = thermostat['weather']['forecasts']
                if not forecasts:
                    return
                if self.type == 'temperature':
                    value = forecasts[0]['temperature']
                    if value != 'unknown':
                        value = float(value) / 10
                elif self.type == 'humidity':
                    value = forecasts[0]['relativeHumidity']
                else:
                    return
                self._state = value
            return

        for sensor in data.ecobee.get_remote_sensors(self.index):
            for item in sensor['capability']:
                if (item['type'] == self.type and
                        self.sensor_name == sensor['name']):
                    if (self.type == 'temperature' and
                            item['value'] != 'unknown'):
                        self._state = float(item['value']) / 10
                    else:
                        self._state = item['value']
