"""
Support for Adafruit DHT temperature and humidity sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dht/
"""
import logging
from datetime import timedelta

from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

# Update this requirement to upstream as soon as it supports Python 3.
REQUIREMENTS = ['http://github.com/mala-zaba/Adafruit_Python_DHT/archive/'
                '4101340de8d2457dd194bca1e8d11cbfc237e919.zip'
                '#Adafruit_DHT==1.1.0']

_LOGGER = logging.getLogger(__name__)
SENSOR_TYPES = {
    'temperature': ['Temperature', None],
    'humidity': ['Humidity', '%']
}
DEFAULT_NAME = "DHT Sensor"
# Return cached results if last scan was less then this time ago
# DHT11 is able to deliver data once per second, DHT22 once every two
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the DHT sensor."""
    # pylint: disable=import-error
    import Adafruit_DHT

    SENSOR_TYPES['temperature'][1] = hass.config.temperature_unit
    unit = hass.config.temperature_unit
    available_sensors = {
        "DHT11": Adafruit_DHT.DHT11,
        "DHT22": Adafruit_DHT.DHT22,
        "AM2302": Adafruit_DHT.AM2302
    }
    sensor = available_sensors[config['sensor']]

    pin = config['pin']

    if not sensor or not pin:
        _LOGGER.error(
            "Config error "
            "Please check your settings for DHT, sensor not supported.")
        return None

    data = DHTClient(Adafruit_DHT, sensor, pin)
    dev = []
    name = config.get('name', DEFAULT_NAME)

    try:
        for variable in config['monitored_conditions']:
            if variable not in SENSOR_TYPES:
                _LOGGER.error('Sensor type: "%s" does not exist', variable)
            else:
                dev.append(DHTSensor(data, variable, unit, name))
    except KeyError:
        pass

    add_devices(dev)


# pylint: disable=too-few-public-methods
class DHTSensor(Entity):
    """Implementation of the DHT sensor."""

    def __init__(self, dht_client, sensor_type, temp_unit, name):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.dht_client = dht_client
        self.temp_unit = temp_unit
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from the DHT and updates the states."""
        self.dht_client.update()
        data = self.dht_client.data

        if self.type == 'temperature':
            self._state = round(data['temperature'], 1)
            if self.temp_unit == TEMP_FAHRENHEIT:
                self._state = round(data['temperature'] * 1.8 + 32, 1)
        elif self.type == 'humidity':
            self._state = round(data['humidity'], 1)


class DHTClient(object):
    """Get the latest data from the DHT sensor."""

    def __init__(self, adafruit_dht, sensor, pin):
        """Initialize the sensor."""
        self.adafruit_dht = adafruit_dht
        self.sensor = sensor
        self.pin = pin
        self.data = dict()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data the DHT sensor."""
        humidity, temperature = self.adafruit_dht.read_retry(self.sensor,
                                                             self.pin)
        if temperature:
            self.data['temperature'] = temperature
        if humidity:
            self.data['humidity'] = humidity
