"""
Support for RESTful binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.rest/
"""
import logging

import voluptuous as vol
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, DEVICE_CLASSES_SCHEMA, PLATFORM_SCHEMA)
from homeassistant.components.sensor.rest import RestData
from homeassistant.const import (
    CONF_PAYLOAD, CONF_NAME, CONF_VALUE_TEMPLATE, CONF_METHOD, CONF_RESOURCE,
    CONF_SENSOR_CLASS, CONF_VERIFY_SSL, CONF_USERNAME, CONF_PASSWORD,
    CONF_HEADERS, CONF_AUTHENTICATION, HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION, CONF_DEVICE_CLASS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.deprecation import get_deprecated

_LOGGER = logging.getLogger(__name__)

DEFAULT_METHOD = 'GET'
DEFAULT_NAME = 'REST Binary Sensor'
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Optional(CONF_AUTHENTICATION):
        vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
    vol.Optional(CONF_HEADERS): {cv.string: cv.string},
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(['POST', 'GET']),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PAYLOAD): cv.string,
    vol.Optional(CONF_SENSOR_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the REST binary sensor."""
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)
    method = config.get(CONF_METHOD)
    payload = config.get(CONF_PAYLOAD)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    headers = config.get(CONF_HEADERS)
    device_class = get_deprecated(config, CONF_DEVICE_CLASS, CONF_SENSOR_CLASS)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass

    if username and password:
        if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = HTTPDigestAuth(username, password)
        else:
            auth = HTTPBasicAuth(username, password)
    else:
        auth = None

    rest = RestData(method, resource, auth, headers, payload, verify_ssl)
    rest.update()

    if rest.data is None:
        _LOGGER.error("Unable to fetch REST data from %s", resource)
        return False

    add_devices([RestBinarySensor(
        hass, rest, name, device_class, value_template)])


class RestBinarySensor(BinarySensorDevice):
    """Representation of a REST binary sensor."""

    def __init__(self, hass, rest, name, device_class, value_template):
        """Initialize a REST binary sensor."""
        self._hass = hass
        self.rest = rest
        self._name = name
        self._device_class = device_class
        self._state = False
        self._previous_data = None
        self._value_template = value_template
        self.update()

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self.rest.data is None:
            return False

        if self._value_template is not None:
            response = self._value_template.\
                async_render_with_possible_json_value(self.rest.data, False)

        try:
            return bool(int(response))
        except ValueError:
            return {'true': True, 'on': True, 'open': True,
                    'yes': True}.get(response.lower(), False)

    def update(self):
        """Get the latest data from REST API and updates the state."""
        self.rest.update()
