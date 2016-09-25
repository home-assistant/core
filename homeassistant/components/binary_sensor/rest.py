"""
Support for RESTful binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.rest/
"""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, SENSOR_CLASSES_SCHEMA, PLATFORM_SCHEMA)
from homeassistant.components.sensor.rest import RestData
from homeassistant.const import (
    CONF_PAYLOAD, CONF_NAME, CONF_VALUE_TEMPLATE, CONF_METHOD, CONF_RESOURCE,
    CONF_SENSOR_CLASS, CONF_VERIFY_SSL)
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_METHOD = 'GET'
DEFAULT_NAME = 'REST Binary Sensor'
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(['POST', 'GET']),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PAYLOAD): cv.string,
    vol.Optional(CONF_SENSOR_CLASS): SENSOR_CLASSES_SCHEMA,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
})


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the REST binary sensor."""
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)
    method = config.get(CONF_METHOD)
    payload = config.get(CONF_PAYLOAD)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    sensor_class = config.get(CONF_SENSOR_CLASS)
    value_template = config.get(CONF_VALUE_TEMPLATE)

    if value_template is not None:
        value_template = template.compile_template(hass, value_template)

    rest = RestData(method, resource, payload, verify_ssl)
    rest.update()

    if rest.data is None:
        _LOGGER.error('Unable to fetch REST data')
        return False

    add_devices([RestBinarySensor(
        hass, rest, name, sensor_class, value_template)])


# pylint: disable=too-many-arguments
class RestBinarySensor(BinarySensorDevice):
    """Representation of a REST binary sensor."""

    def __init__(self, hass, rest, name, sensor_class, value_template):
        """Initialize a REST binary sensor."""
        self._hass = hass
        self.rest = rest
        self._name = name
        self._sensor_class = sensor_class
        self._state = False
        self._previous_data = None
        self._value_template = value_template
        self.update()

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def sensor_class(self):
        """Return the class of this sensor."""
        return self._sensor_class

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self.rest.data is None:
            return False

        if self._value_template is not None:
            response = template.render_with_possible_json_value(
                self._hass, self._value_template, self.rest.data, False)

        try:
            return bool(int(response))
        except ValueError:
            return {"true": True, "on": True, "open": True,
                    "yes": True}.get(response.lower(), False)

    def update(self):
        """Get the latest data from REST API and updates the state."""
        self.rest.update()
