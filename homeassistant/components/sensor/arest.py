"""
homeassistant.components.sensor.arest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The arest sensor will consume an exposed aREST API of a device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.arest/
"""
from datetime import timedelta
import logging

import requests

from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

CONF_RESOURCE = 'resource'
CONF_MONITORED_VARIABLES = 'monitored_variables'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the aREST sensor. """

    resource = config.get(CONF_RESOURCE)
    var_conf = config.get(CONF_MONITORED_VARIABLES)
    pins = config.get('pins', None)

    if resource is None:
        _LOGGER.error('Not all required config keys present: %s',
                      CONF_RESOURCE)
        return False

    try:
        response = requests.get(resource, timeout=10).json()
    except requests.exceptions.MissingSchema:
        _LOGGER.error("Missing resource or schema in configuration. "
                      "Add http:// to your URL.")
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to device at %s. "
                      "Please check the IP address in the configuration file.",
                      resource)
        return False

    arest = ArestData(resource)

    dev = []

    if var_conf is not None:
        for variable in config['monitored_variables']:
            if variable['name'] not in response['variables']:
                _LOGGER.error('Variable: "%s" does not exist',
                              variable['name'])
                continue

            dev.append(ArestSensor(arest,
                                   resource,
                                   config.get('name', response['name']),
                                   variable['name'],
                                   variable=variable['name'],
                                   unit_of_measurement=variable.get(
                                       'unit_of_measurement')))

    if pins is not None:
        for pinnum, pin in pins.items():
            dev.append(ArestSensor(ArestData(resource, pinnum),
                                   resource,
                                   config.get('name', response['name']),
                                   pin.get('name'),
                                   pin=pinnum,
                                   unit_of_measurement=pin.get(
                                       'unit_of_measurement'),
                                   corr_factor=pin.get('correction_factor',
                                                       None),
                                   decimal_places=pin.get('decimal_places',
                                                          None)))

    add_devices(dev)


# pylint: disable=too-many-instance-attributes, too-many-arguments
class ArestSensor(Entity):
    """ Implements an aREST sensor for exposed variables. """

    def __init__(self, arest, resource, location, name, variable=None,
                 pin=None, unit_of_measurement=None, corr_factor=None,
                 decimal_places=None):
        self.arest = arest
        self._resource = resource
        self._name = '{} {}'.format(location.title(), name.title()) \
                     or DEVICE_DEFAULT_NAME
        self._variable = variable
        self._pin = pin
        self._state = 'n/a'
        self._unit_of_measurement = unit_of_measurement
        self._corr_factor = corr_factor
        self._decimal_places = decimal_places
        self.update()

        if self._pin is not None:
            request = requests.get('{}/mode/{}/i'.format
                                   (self._resource, self._pin), timeout=10)
            if request.status_code is not 200:
                _LOGGER.error("Can't set mode. Is device offline?")

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
        elif 'value' in values:
            if self._corr_factor is not None \
                    and self._decimal_places is not None:
                return round((float(values['value']) *
                              float(self._corr_factor)), self._decimal_places)
            elif self._corr_factor is not None \
                    and self._decimal_places is None:
                return round(float(values['value']) * float(self._corr_factor))
            else:
                return values['value']
        else:
            return values.get(self._variable, 'n/a')

    def update(self):
        """ Gets the latest data from aREST API. """
        self.arest.update()


# pylint: disable=too-few-public-methods
class ArestData(object):
    """ Class for handling the data retrieval for variables. """

    def __init__(self, resource, pin=None):
        self._resource = resource
        self._pin = pin
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from aREST device. """
        try:
            if self._pin is None:
                response = requests.get(self._resource, timeout=10)
                self.data = response.json()['variables']
            else:
                try:
                    if str(self._pin[0]) == 'A':
                        response = requests.get('{}/analog/{}'.format(
                            self._resource, self._pin[1:]), timeout=10)
                        self.data = {'value': response.json()['return_value']}
                    else:
                        _LOGGER.error("Wrong pin naming. "
                                      "Please check your configuration file.")
                except TypeError:
                    response = requests.get('{}/digital/{}'.format(
                        self._resource, self._pin), timeout=10)
                    self.data = {'value': response.json()['return_value']}
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to device %s. Is device offline?",
                          self._resource)
            self.data = {'error': 'error fetching'}
