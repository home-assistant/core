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

Details for the API : http://arest.io

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
from requests import get, exceptions

from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the aREST sensor. """

    resource = config.get('resource', None)

    try:
        response = get(resource)
    except exceptions.MissingSchema:
        _LOGGER.error("Missing resource or schema in configuration. "
                      "Add http:// to your URL.")
        return False
    except exceptions.ConnectionError:
        _LOGGER.error("No route to device. "
                      "Please check the IP address in the configuration file.")
        return False

    data = ArestData(resource)

    dev = []
    for variable in config['monitored_variables']:
        if 'unit' not in variable:
            variable['unit'] = ' '
        if variable['name'] not in response.json()['variables']:
            _LOGGER.error('Variable: "%s" does not exist', variable['name'])
        else:
            dev.append(ArestSensor(data,
                                   response.json()['name'],
                                   variable['name'],
                                   variable['unit']))

    add_devices(dev)


class ArestSensor(Entity):
    """ Implements an aREST sensor. """

    def __init__(self, data, location, variable, unit_of_measurement):
        self._data = data
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
        return self._state

    def update(self):
        """ Gets the latest data from aREST API and updates the states. """
        values = self._data.update()
        if values is not None:
            self._state = values[self._variable]
        else:
            self._state = 'n/a'


# pylint: disable=too-few-public-methods
class ArestData(object):
    """ Class for handling the data retrieval. """

    def __init__(self, resource):
        self.resource = resource

    def update(self):
        """ Gets the latest data from aREST API. """
        try:
            response = get(self.resource)
            return response.json()['variables']
        except exceptions.ConnectionError:
            _LOGGER.error("No route to device. Is device offline?")
            return None
