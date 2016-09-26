"""
The arest sensor will consume an exposed aREST API of a device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.arest/
"""
import logging
from datetime import timedelta

import requests

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE, DEVICE_DEFAULT_NAME,
    CONF_RESOURCE, CONF_MONITORED_VARIABLES)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import template
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the aREST sensor."""
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

    def make_renderer(value_template):
        """Create a renderer based on variable_template value."""
        if value_template is None:
            return lambda value: value

        value_template = template.Template(value_template, hass)

        def _render(value):
            try:
                return value_template.render({'value': value})
            except TemplateError:
                _LOGGER.exception('Error parsing value')
                return value

        return _render

    dev = []

    if var_conf is not None:
        for variable in var_conf:
            if variable['name'] not in response['variables']:
                _LOGGER.error('Variable: "%s" does not exist',
                              variable['name'])
                continue

            renderer = make_renderer(variable.get(CONF_VALUE_TEMPLATE))
            dev.append(ArestSensor(arest,
                                   resource,
                                   config.get('name', response['name']),
                                   variable['name'],
                                   variable=variable['name'],
                                   unit_of_measurement=variable.get(
                                       ATTR_UNIT_OF_MEASUREMENT),
                                   renderer=renderer))

    if pins is not None:
        for pinnum, pin in pins.items():
            renderer = make_renderer(pin.get(CONF_VALUE_TEMPLATE))
            dev.append(ArestSensor(ArestData(resource, pinnum),
                                   resource,
                                   config.get('name', response['name']),
                                   pin.get('name'),
                                   pin=pinnum,
                                   unit_of_measurement=pin.get(
                                       ATTR_UNIT_OF_MEASUREMENT),
                                   renderer=renderer))

    add_devices(dev)


# pylint: disable=too-many-instance-attributes, too-many-arguments
class ArestSensor(Entity):
    """Implementation of an aREST sensor for exposed variables."""

    def __init__(self, arest, resource, location, name, variable=None,
                 pin=None, unit_of_measurement=None, renderer=None):
        """Initialize the sensor."""
        self.arest = arest
        self._resource = resource
        self._name = '{} {}'.format(location.title(), name.title()) \
                     or DEVICE_DEFAULT_NAME
        self._variable = variable
        self._pin = pin
        self._state = 'n/a'
        self._unit_of_measurement = unit_of_measurement
        self._renderer = renderer
        self.update()

        if self._pin is not None:
            request = requests.get('{}/mode/{}/i'.format
                                   (self._resource, self._pin), timeout=10)
            if request.status_code is not 200:
                _LOGGER.error("Can't set mode. Is device offline?")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        values = self.arest.data

        if 'error' in values:
            return values['error']

        value = self._renderer(values.get('value',
                                          values.get(self._variable,
                                                     'N/A')))
        return value

    def update(self):
        """Get the latest data from aREST API."""
        self.arest.update()


# pylint: disable=too-few-public-methods
class ArestData(object):
    """The Class for handling the data retrieval for variables."""

    def __init__(self, resource, pin=None):
        """Initialize the data object."""
        self._resource = resource
        self._pin = pin
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from aREST device."""
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
