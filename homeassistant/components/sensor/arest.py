"""
homeassistant.components.sensor.arest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The arest sensor will consume an exposed aREST API of a device.

Configuration:

To use the arest sensor you will need to add something like the following
to your configuration.yaml file.

sensor:
  platform: arest
  resource: http://IP_ADDRESS
  monitored_variables:
    - name: temperature
      unit: '°C'
    - name: humidity
      unit: '%'

Variables:

resource:
*Required
IP address of the device that is exposing an aREST API.

These are the variables for the monitored_variables array:

name
*Required
The name of the variable you wish to monitor.

unit
*Optional
Defines the units of measurement of the sensor, if any.

Details for the API: http://arest.io

Format of a default JSON response by aREST:
{
   "variables":{
      "temperature":21,
      "humidity":89
   },
   "id":"device008",
   "name":"Bedroom",
   "connected":true
}
"""
import logging
import requests
from datetime import timedelta

from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONF_RESOURCE = 'resource'
CONF_MONITORED_VARIABLES = 'monitored_variables'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the aREST sensor. """

    resource = config.get(CONF_RESOURCE)
    var_conf = config.get(CONF_MONITORED_VARIABLES)

    if None in (resource, var_conf):
        _LOGGER.error('Not all required config keys present: %s',
                      ', '.join((CONF_RESOURCE, CONF_MONITORED_VARIABLES)))
        return False

    try:
        response = requests.get(resource, timeout=10).json()
    except requests.exceptions.MissingSchema:
        _LOGGER.error("Missing resource or schema in configuration. "
                      "Add http:// to your URL.")
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to device. "
                      "Please check the IP address in the configuration file.")
        return False

    arest = ArestData(resource)

    dev = []
    for variable in config['monitored_variables']:
        if variable['name'] not in response['variables']:
            _LOGGER.error('Variable: "%s" does not exist', variable['name'])
            continue

        dev.append(ArestSensor(arest, response['name'], variable['name'],
                               variable.get('unit')))

    add_devices(dev)


class ArestSensor(Entity):
    """ Implements an aREST sensor. """

    def __init__(self, arest, location, variable, unit_of_measurement):
        self.arest = arest
        self._name = '{} {}'.format(location.title(), variable.title())
        self._variable = variable
        self._state = 'n/a'
        self._unit_of_measurement = unit_of_measurement
        self.update()

    @property
    def name(self):
        """ The name of the sensor. """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Unit the value is expressed in. """
        return self._unit_of_measurement

    @property
    def state(self):
        """ Returns the state of the device. """
        values = self.arest.data

        if 'error' in values:
            return values['error']
        else:
            return values.get(self._variable, 'n/a')

    def update(self):
        """ Gets the latest data from aREST API. """
        self.arest.update()


# pylint: disable=too-few-public-methods
class ArestData(object):
    """ Class for handling the data retrieval. """

    def __init__(self, resource):
        self.resource = resource
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from aREST device. """
        try:
            response = requests.get(self.resource, timeout=10)
            self.data = response.json()['variables']
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to device. Is device offline?")
            self.data = {'error': 'error fetching'}
