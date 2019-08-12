"""Support for RESTful API sensors."""
import logging
import json

import voluptuous as vol
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA)
from homeassistant.const import (
    CONF_AUTHENTICATION, CONF_FORCE_UPDATE, CONF_HEADERS, CONF_NAME,
    CONF_METHOD, CONF_PASSWORD, CONF_PAYLOAD, CONF_RESOURCE,
    CONF_UNIT_OF_MEASUREMENT, CONF_USERNAME, CONF_TIMEOUT,
    CONF_VALUE_TEMPLATE, CONF_VERIFY_SSL, CONF_DEVICE_CLASS,
    HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_METHOD = 'GET'
DEFAULT_NAME = 'REST Sensor'
DEFAULT_VERIFY_SSL = True
DEFAULT_FORCE_UPDATE = False
DEFAULT_TIMEOUT = 10

CONF_JSON_ATTRS = 'json_attributes'
METHODS = ['POST', 'GET']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Optional(CONF_AUTHENTICATION):
        vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
    vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.string}),
    vol.Optional(CONF_JSON_ATTRS, default=[]): cv.ensure_list_csv,
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(METHODS),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PAYLOAD): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RESTful sensor."""
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)
    method = config.get(CONF_METHOD)
    payload = config.get(CONF_PAYLOAD)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    headers = config.get(CONF_HEADERS)
    unit = config.get(CONF_UNIT_OF_MEASUREMENT)
    device_class = config.get(CONF_DEVICE_CLASS)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    json_attrs = config.get(CONF_JSON_ATTRS)
    force_update = config.get(CONF_FORCE_UPDATE)
    timeout = config.get(CONF_TIMEOUT)

    if value_template is not None:
        value_template.hass = hass

    if username and password:
        if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = HTTPDigestAuth(username, password)
        else:
            auth = HTTPBasicAuth(username, password)
    else:
        auth = None
    rest = RestData(method, resource, auth, headers, payload, verify_ssl,
                    timeout)
    rest.update()
    if rest.data is None:
        raise PlatformNotReady

    # Must update the sensor now (including fetching the rest resource) to
    # ensure it's updating its state.
    add_entities([RestSensor(
        hass, rest, name, unit, device_class,
        value_template, json_attrs, force_update
    )], True)


class RestSensor(Entity):
    """Implementation of a REST sensor."""

    def __init__(self, hass, rest, name, unit_of_measurement,
                 device_class, value_template, json_attrs, force_update):
        """Initialize the REST sensor."""
        self._hass = hass
        self.rest = rest
        self._name = name
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self._device_class = device_class
        self._value_template = value_template
        self._json_attrs = json_attrs
        self._attributes = None
        self._force_update = force_update

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def available(self):
        """Return if the sensor data are available."""
        return self.rest.data is not None

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    def update(self):
        """Get the latest data from REST API and update the state."""
        self.rest.update()
        value = self.rest.data

        if self._json_attrs:
            self._attributes = {}
            if value:
                try:
                    json_dict = json.loads(value)
                    if isinstance(json_dict, dict):
                        attrs = {k: json_dict[k] for k in self._json_attrs
                                 if k in json_dict}
                        self._attributes = attrs
                    else:
                        _LOGGER.warning("JSON result was not a dictionary")
                except ValueError:
                    _LOGGER.warning("REST result could not be parsed as JSON")
                    _LOGGER.debug("Erroneous JSON: %s", value)
            else:
                _LOGGER.warning("Empty reply found when expecting JSON data")
        if value is not None and self._value_template is not None:
            value = self._value_template.render_with_possible_json_value(
                value, None)

        self._state = value

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes


class RestData:
    """Class for handling the data retrieval."""

    def __init__(self, method, resource, auth, headers, data, verify_ssl,
                 timeout=DEFAULT_TIMEOUT):
        """Initialize the data object."""
        self._request = requests.Request(
            method, resource, headers=headers, auth=auth, data=data).prepare()
        self._verify_ssl = verify_ssl
        self._timeout = timeout
        self.data = None

    def update(self):
        """Get the latest data from REST service with provided method."""
        _LOGGER.debug("Updating from %s", self._request.url)
        try:
            with requests.Session() as sess:
                response = sess.send(
                    self._request, timeout=self._timeout,
                    verify=self._verify_ssl)

            self.data = response.text
        except requests.exceptions.RequestException as ex:
            _LOGGER.error("Error fetching data: %s from %s failed with %s",
                          self._request, self._request.url, ex)
            self.data = None
