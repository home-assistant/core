"""
homeassistant.components.sensor.rest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The rest sensor will consume JSON responses sent by an exposed REST API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rest.html
"""
import logging
import requests
from json import loads
from datetime import timedelta

from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'REST Sensor'
DEFAULT_METHOD = 'GET'

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the REST sensor. """

    use_get = False
    use_post = False

    resource = config.get('resource', None)
    method = config.get('method', DEFAULT_METHOD)
    payload = config.get('payload', None)
    verify_ssl = config.get('verify_ssl', True)

    if method == 'GET':
        use_get = True
    elif method == 'POST':
        use_post = True

    try:
        if use_get:
            response = requests.get(resource, timeout=10, verify=verify_ssl)
        elif use_post:
            response = requests.post(resource, data=payload, timeout=10,
                                     verify=verify_ssl)
        if not response.ok:
            _LOGGER.error('Response status is "%s"', response.status_code)
            return False
    except requests.exceptions.MissingSchema:
        _LOGGER.error('Missing resource or schema in configuration. '
                      'Add http:// to your URL.')
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error('No route to resource/endpoint. '
                      'Please check the URL in the configuration file.')
        return False

    try:
        data = loads(response.text)
    except ValueError:
        _LOGGER.error('No valid JSON in the response in: %s', data)
        return False

    try:
        RestSensor.extract_value(data, config.get('variable'))
    except KeyError:
        _LOGGER.error('Variable "%s" not found in response: "%s"',
                      config.get('variable'), data)
        return False

    if use_get:
        rest = RestDataGet(resource, verify_ssl)
    elif use_post:
        rest = RestDataPost(resource, payload, verify_ssl)

    add_devices([RestSensor(rest,
                            config.get('name', DEFAULT_NAME),
                            config.get('variable'),
                            config.get('unit_of_measurement'),
                            config.get('correction_factor', None),
                            config.get('decimal_places', None))])


# pylint: disable=too-many-arguments
class RestSensor(Entity):
    """ Implements a REST sensor. """

    def __init__(self, rest, name, variable, unit_of_measurement, corr_factor,
                 decimal_places):
        self.rest = rest
        self._name = name
        self._variable = variable
        self._state = 'n/a'
        self._unit_of_measurement = unit_of_measurement
        self._corr_factor = corr_factor
        self._decimal_places = decimal_places
        self.update()

    @classmethod
    def extract_value(cls, data, variable):
        """ Extracts the value using a key name or a path. """
        if isinstance(variable, list):
            for variable_item in variable:
                data = data[variable_item]
            return data
        else:
            return data[variable]

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
            try:
                if value is not None:
                    value = RestSensor.extract_value(value, self._variable)
                    if self._corr_factor is not None \
                            and self._decimal_places is not None:
                        self._state = round(
                            (float(value) *
                             float(self._corr_factor)),
                            self._decimal_places)
                    elif self._corr_factor is not None \
                            and self._decimal_places is None:
                        self._state = round(float(value) *
                                            float(self._corr_factor))
                    else:
                        self._state = value
            except ValueError:
                self._state = RestSensor.extract_value(value, self._variable)


# pylint: disable=too-few-public-methods
class RestDataGet(object):
    """ Class for handling the data retrieval with GET method. """

    def __init__(self, resource, verify_ssl):
        self._resource = resource
        self._verify_ssl = verify_ssl
        self.data = dict()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from REST service with GET method. """
        try:
            response = requests.get(self._resource, timeout=10,
                                    verify=self._verify_ssl)
            if 'error' in self.data:
                del self.data['error']
            self.data = response.json()
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to resource/endpoint.")
            self.data['error'] = 'N/A'


# pylint: disable=too-few-public-methods
class RestDataPost(object):
    """ Class for handling the data retrieval with POST method. """

    def __init__(self, resource, payload, verify_ssl):
        self._resource = resource
        self._payload = payload
        self._verify_ssl = verify_ssl
        self.data = dict()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from REST service with POST method. """
        try:
            response = requests.post(self._resource, data=self._payload,
                                     timeout=10, verify=self._verify_ssl)
            if 'error' in self.data:
                del self.data['error']
            self.data = response.json()
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to resource/endpoint.")
            self.data['error'] = 'N/A'
