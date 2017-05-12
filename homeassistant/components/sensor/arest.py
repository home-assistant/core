"""
Support for an exposed aREST RESTful API of a device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.arest/
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE, CONF_RESOURCE,
    CONF_MONITORED_VARIABLES, CONF_NAME, STATE_UNKNOWN)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

CONF_FUNCTIONS = 'functions'
CONF_PINS = 'pins'

DEFAULT_NAME = 'aREST sensor'

PIN_VARIABLE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PINS, default={}):
        vol.Schema({cv.string: PIN_VARIABLE_SCHEMA}),
    vol.Optional(CONF_MONITORED_VARIABLES, default={}):
        vol.Schema({cv.string: PIN_VARIABLE_SCHEMA}),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the aREST sensor."""
    resource = config.get(CONF_RESOURCE)
    var_conf = config.get(CONF_MONITORED_VARIABLES)
    pins = config.get(CONF_PINS)

    try:
        response = requests.get(resource, timeout=10).json()
    except requests.exceptions.MissingSchema:
        _LOGGER.error("Missing resource or schema in configuration. "
                      "Add http:// to your URL")
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to device at %s", resource)
        return False

    arest = ArestData(resource)

    def make_renderer(value_template):
        """Create a renderer based on variable_template value."""
        if value_template is None:
            return lambda value: value

        value_template.hass = hass

        def _render(value):
            try:
                return value_template.async_render({'value': value})
            except TemplateError:
                _LOGGER.exception("Error parsing value")
                return value

        return _render

    dev = []

    if var_conf is not None:
        for variable, var_data in var_conf.items():
            if variable not in response['variables']:
                _LOGGER.error("Variable: %s does not exist", variable)
                continue

            renderer = make_renderer(var_data.get(CONF_VALUE_TEMPLATE))
            dev.append(ArestSensor(
                arest, resource, config.get(CONF_NAME, response[CONF_NAME]),
                var_data.get(CONF_NAME, variable), variable=variable,
                unit_of_measurement=var_data.get(CONF_UNIT_OF_MEASUREMENT),
                renderer=renderer))

    if pins is not None:
        for pinnum, pin in pins.items():
            renderer = make_renderer(pin.get(CONF_VALUE_TEMPLATE))
            dev.append(ArestSensor(
                ArestData(resource, pinnum), resource,
                config.get(CONF_NAME, response[CONF_NAME]), pin.get(CONF_NAME),
                pin=pinnum, unit_of_measurement=pin.get(
                    CONF_UNIT_OF_MEASUREMENT), renderer=renderer))

    add_devices(dev)


class ArestSensor(Entity):
    """Implementation of an aREST sensor for exposed variables."""

    def __init__(self, arest, resource, location, name, variable=None,
                 pin=None, unit_of_measurement=None, renderer=None):
        """Initialize the sensor."""
        self.arest = arest
        self._resource = resource
        self._name = '{} {}'.format(location.title(), name.title())
        self._variable = variable
        self._pin = pin
        self._state = STATE_UNKNOWN
        self._unit_of_measurement = unit_of_measurement
        self._renderer = renderer
        self.update()

        if self._pin is not None:
            request = requests.get(
                '{}/mode/{}/i'.format(self._resource, self._pin), timeout=10)
            if request.status_code is not 200:
                _LOGGER.error("Can't set mode of %s", self._resource)

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

        value = self._renderer(
            values.get('value', values.get(self._variable, STATE_UNKNOWN)))
        return value

    def update(self):
        """Get the latest data from aREST API."""
        self.arest.update()

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.arest.available


class ArestData(object):
    """The Class for handling the data retrieval for variables."""

    def __init__(self, resource, pin=None):
        """Initialize the data object."""
        self._resource = resource
        self._pin = pin
        self.data = {}
        self.available = True

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
                except TypeError:
                    response = requests.get('{}/digital/{}'.format(
                        self._resource, self._pin), timeout=10)
                    self.data = {'value': response.json()['return_value']}
            self.available = True
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to device %s", self._resource)
            self.available = False
