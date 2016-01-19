"""
homeassistant.components.sensor.ecobee
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ecobee Thermostat Component

This component adds support for Ecobee3 Wireless Thermostats.
You will need to setup developer access to your thermostat,
and create and API key on the ecobee website.

The first time you run this component you will see a configuration
component card in Home Assistant.  This card will contain a PIN code
that you will need to use to authorize access to your thermostat.  You
can do this at https://www.ecobee.com/consumerportal/index.html
Click My Apps, Add application, Enter Pin and click Authorize.

After authorizing the application click the button in the configuration
card.  Now your thermostat and sensors should shown in home-assistant.

You can use the optional hold_temp parameter to set whether or not holds
are set indefintely or until the next scheduled event.

ecobee:
  api_key: asdfasdfasdfasdfasdfaasdfasdfasdfasdf
  hold_temp: True

"""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.components import ecobee
from homeassistant.const import TEMP_FAHRENHEIT

DEPENDENCIES = ['ecobee']

SENSOR_TYPES = {
    'temperature': ['Temperature', TEMP_FAHRENHEIT],
    'humidity': ['Humidity', '%'],
    'occupancy': ['Occupancy', None]
}

_LOGGER = logging.getLogger(__name__)

ECOBEE_CONFIG_FILE = 'ecobee.conf'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the sensors. """
    if discovery_info is None:
        return
    data = ecobee.NETWORK
    dev = list()
    for index in range(len(data.ecobee.thermostats)):
        for sensor in data.ecobee.get_remote_sensors(index):
            for item in sensor['capability']:
                if item['type'] not in ('temperature',
                                        'humidity', 'occupancy'):
                    continue

                dev.append(EcobeeSensor(sensor['name'], item['type'], index))

    add_devices(dev)


class EcobeeSensor(Entity):
    """ An ecobee sensor. """

    def __init__(self, sensor_name, sensor_type, sensor_index):
        self._name = sensor_name + ' ' + SENSOR_TYPES[sensor_type][0]
        self.sensor_name = sensor_name
        self.type = sensor_type
        self.index = sensor_index
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

    @property
    def name(self):
        return self._name.rstrip()

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    def update(self):
        data = ecobee.NETWORK
        data.update()
        for sensor in data.ecobee.get_remote_sensors(self.index):
            for item in sensor['capability']:
                if (
                        item['type'] == self.type and
                        self.type == 'temperature' and
                        self.sensor_name == sensor['name']):
                    self._state = float(item['value']) / 10
                elif (
                        item['type'] == self.type and
                        self.type == 'humidity' and
                        self.sensor_name == sensor['name']):
                    self._state = item['value']
                elif (
                        item['type'] == self.type and
                        self.type == 'occupancy' and
                        self.sensor_name == sensor['name']):
                    self._state = item['value']
