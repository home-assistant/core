"""
homeassistant.components.sensor.rest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The rest sensor will consume JSON responses sent by an exposed REST API.

Configuration:

To use the rest sensor you will need to add something like the following
to your configuration.yaml file.

sensor:
  platform: arest
    name: REST sensor
    resource: http://IP_ADDRESS/ENDPOINT
    variable: temperature
    unit: '°C'

Variables:

name
*Optional
The name of the sensor. Default is 'REST Sensor'.

resource
*Required
The full URL of the REST service/endpoint that provide the JSON response.

variable
*Required
The name of the variable inside the JSON response you want to monitor.

unit
*Optional
Defines the units of measurement of the sensor, if any.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rest.html
"""
import logging
from requests import get, exceptions
from json import loads
from datetime import timedelta

from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "REST Sensor"

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the REST sensor. """

    resource = config.get('resource', None)

    try:
        response = get(resource, timeout=10)
        if not response.ok:
            _LOGGER.error('Response status is "%s"', response.status_code)
            return False
    except exceptions.MissingSchema:
        _LOGGER.error('Missing resource or schema in configuration. '
                      'Add http:// to your URL.')
        return False
    except exceptions.ConnectionError:
        _LOGGER.error('No route to resource/endpoint. '
                      'Please check the URL in the configuration file.')
        return False

    try:
        data = loads(response.text)
    except ValueError:
        _LOGGER.error('No valid JSON in the response in: %s', data)
        return False

    try:
        data[config.get('variable')]
    except KeyError:
        _LOGGER.error('Variable "%s" not found in response: "%s"',
                      config.get('variable'), data)
        return False

    rest = RestData(resource)

    add_devices([RestSensor(rest,
                            config.get('name', DEFAULT_NAME),
                            config.get('variable'),
                            config.get('unit'))])


class RestSensor(Entity):
    """ Implements a REST sensor. """

    def __init__(self, rest, name, variable, unit_of_measurement):
        self.rest = rest
        self._name = name
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
        """ Gets the latest data from REST API and updates the state. """
        self.rest.update()
        value = self.rest.data

        if 'error' in value:
            self._state = value['error']
        else:
            self._state = value[self._variable]


# pylint: disable=too-few-public-methods
class RestData(object):
    """ Class for handling the data retrieval. """

    def __init__(self, resource):
        self.resource = resource
        self.data = dict()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from REST service. """
        try:
            response = get(self.resource, timeout=10)
            if 'error' in self.data:
                del self.data['error']
            self.data = response.json()
        except exceptions.ConnectionError:
            _LOGGER.error("No route to resource/endpoint.")
            self.data['error'] = 'N/A'
