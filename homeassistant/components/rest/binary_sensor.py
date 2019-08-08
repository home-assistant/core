"""Support for RESTful binary sensors."""
import json
import logging

from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorDevice,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_RESOURCE,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, template

from .sensor import (CONF_JSON_ATTRS, DEFAULT_FORCE_UPDATE, RestData)

_LOGGER = logging.getLogger(__name__)

DEFAULT_METHOD = "GET"
DEFAULT_NAME = "REST Binary Sensor"
DEFAULT_VERIFY_SSL = True
DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCE): cv.url,
        vol.Optional(CONF_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_HEADERS): {cv.string: cv.string},
        vol.Optional(CONF_JSON_ATTRS): vol.Any(cv.template_complex, cv.template),
        vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(["POST", "GET"]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PAYLOAD): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the REST binary sensor."""
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)
    method = config.get(CONF_METHOD)
    payload = config.get(CONF_PAYLOAD)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    timeout = config.get(CONF_TIMEOUT)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    headers = config.get(CONF_HEADERS)
    device_class = config.get(CONF_DEVICE_CLASS)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    json_attrs = config.get(CONF_JSON_ATTRS)
    force_update = config.get(CONF_FORCE_UPDATE)

    if value_template is not None:
        value_template.hass = hass

    template.attach(hass, json_attrs)

    if username and password:
        if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = HTTPDigestAuth(username, password)
        else:
            auth = HTTPBasicAuth(username, password)
    else:
        auth = None

    rest = RestData(method, resource, auth, headers, payload, verify_ssl, timeout)
    rest.update()
    if rest.data is None:
        raise PlatformNotReady

    # No need to update the sensor now because it will determine its state
    # based in the rest resource that has just been retrieved.
    add_entities([RestBinarySensor(
        hass, rest, name, device_class,
        value_template, json_attrs, force_update)])


class RestBinarySensor(BinarySensorDevice):
    """Representation of a REST binary sensor."""

    def __init__(self, hass, rest, name, device_class, value_template,
                 json_attrs, force_update):
        """Initialize a REST binary sensor."""
        self._hass = hass
        self.rest = rest
        self._name = name
        self._device_class = device_class
        self._state = False
        self._previous_data = None
        self._value_template = value_template
        self._json_attrs = json_attrs
        self._attributes = None
        self._force_update = force_update

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def available(self):
        """Return the availability of this sensor."""
        return self.rest.data is not None

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self.rest.data is None:
            return False

        response = self.rest.data

        if self._value_template is not None:
            response = self._value_template.async_render_with_possible_json_value(
                self.rest.data, False
            )

        try:
            return bool(int(response))
        except ValueError:
            return {"true": True, "on": True, "open": True, "yes": True}.get(
                response.lower(), False
            )

    def update(self):
        """Get the latest data from REST API and updates the state."""
        self.rest.update()
        value = self.rest.data

        self._attributes = {}
        attr = {}

        if self._json_attrs and value:
            try:
                if isinstance(self._json_attrs, template.Template):
                    attr = self._json_attrs. \
                        render_with_possible_json_value(value)
                elif isinstance(self._json_attrs, dict):
                    json_dict = {}
                    try:
                        json_dict = json.loads(value)
                    except (ValueError, TypeError):
                        _LOGGER.warning("REST result could not be parsed "
                                        "as JSON")
                        _LOGGER.debug("Erroneous JSON: %s", value)
                    else:
                        attr.update(
                            template.render_complex(self._json_attrs,
                                                    {'value': value,
                                                     'value_json': json_dict}))
                self._attributes = attr
            except (exceptions.TemplateError, vol.Invalid) as ex:
                _LOGGER.error("Error rendering '%s' for template: %s",
                              self.name, ex)
        if value is not None and self._value_template is not None:
            value = self._value_template.render_with_possible_json_value(
                value, None)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes
