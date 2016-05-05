"""
Support for REST API sensors..

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rest/
"""
import logging

import requests

from homeassistant.const import CONF_VALUE_TEMPLATE, STATE_UNKNOWN
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'REST Sensor'
DEFAULT_METHOD = 'GET'


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the REST sensor."""
    resource = config.get('resource', None)
    method = config.get('method', DEFAULT_METHOD)
    payload = config.get('payload', None)
    verify_ssl = config.get('verify_ssl', True)

    rest = RestData(method, resource, payload, verify_ssl)
    rest.update()

    if rest.data is None:
        _LOGGER.error('Unable to fetch Rest data')
        return False

    add_devices([RestSensor(
        hass, rest, config.get('name', DEFAULT_NAME),
        config.get('unit_of_measurement'), config.get(CONF_VALUE_TEMPLATE))])


# pylint: disable=too-many-arguments
class RestSensor(Entity):
    """Implementation of a REST sensor."""

    def __init__(self, hass, rest, name, unit_of_measurement, value_template):
        """Initialize the sensor."""
        self._hass = hass
        self.rest = rest
        self._name = name
        self._state = STATE_UNKNOWN
        self._unit_of_measurement = unit_of_measurement
        self._value_template = value_template
        self.update()

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
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest data from REST API and update the state."""
        self.rest.update()
        value = self.rest.data

        if value is None:
            value = STATE_UNKNOWN
        elif self._value_template is not None:
            value = template.render_with_possible_json_value(
                self._hass, self._value_template, value, STATE_UNKNOWN)

        self._state = value


# pylint: disable=too-few-public-methods
class RestData(object):
    """Class for handling the data retrieval."""

    def __init__(self, method, resource, data, verify_ssl):
        """Initialize the data object."""
        self._request = requests.Request(method, resource, data=data).prepare()
        self._verify_ssl = verify_ssl
        self.data = None

    def update(self):
        """Get the latest data from REST service with GET method."""
        try:
            with requests.Session() as sess:
                response = sess.send(self._request, timeout=10,
                                     verify=self._verify_ssl)

            self.data = response.text
        except requests.exceptions.RequestException:
            _LOGGER.error("Error fetching data: %s", self._request)
            self.data = None
