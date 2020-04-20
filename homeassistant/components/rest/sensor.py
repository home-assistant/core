"""Support for RESTful API sensors."""
import json
import logging
from xml.parsers.expat import ExpatError

from jsonpath import jsonpath
import requests
from requests import Session
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol
import xmltodict

from homeassistant.components.sensor import DEVICE_CLASSES_SCHEMA, PLATFORM_SCHEMA
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
    CONF_RESOURCE_TEMPLATE,
    CONF_TIMEOUT,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_METHOD = "GET"
DEFAULT_NAME = "REST Sensor"
DEFAULT_VERIFY_SSL = True
DEFAULT_FORCE_UPDATE = False
DEFAULT_TIMEOUT = 10


CONF_JSON_ATTRS = "json_attributes"
CONF_JSON_ATTRS_PATH = "json_attributes_path"
METHODS = ["POST", "GET"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Exclusive(CONF_RESOURCE, CONF_RESOURCE): cv.url,
        vol.Exclusive(CONF_RESOURCE_TEMPLATE, CONF_RESOURCE): cv.template,
        vol.Optional(CONF_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_JSON_ATTRS, default=[]): cv.ensure_list_csv,
        vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(METHODS),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PAYLOAD): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_JSON_ATTRS_PATH): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE), PLATFORM_SCHEMA
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RESTful sensor."""
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)
    resource_template = config.get(CONF_RESOURCE_TEMPLATE)
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
    json_attrs_path = config.get(CONF_JSON_ATTRS_PATH)
    force_update = config.get(CONF_FORCE_UPDATE)
    timeout = config.get(CONF_TIMEOUT)

    if value_template is not None:
        value_template.hass = hass

    if resource_template is not None:
        resource_template.hass = hass
        resource = resource_template.render()

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

    # Must update the sensor now (including fetching the rest resource) to
    # ensure it's updating its state.
    add_entities(
        [
            RestSensor(
                hass,
                rest,
                name,
                unit,
                device_class,
                value_template,
                json_attrs,
                force_update,
                resource_template,
                json_attrs_path,
            )
        ],
        True,
    )


class RestSensor(Entity):
    """Implementation of a REST sensor."""

    def __init__(
        self,
        hass,
        rest,
        name,
        unit_of_measurement,
        device_class,
        value_template,
        json_attrs,
        force_update,
        resource_template,
        json_attrs_path,
    ):
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
        self._resource_template = resource_template
        self._json_attrs_path = json_attrs_path

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
        if self._resource_template is not None:
            self.rest.set_url(self._resource_template.render())

        self.rest.update()
        value = self.rest.data
        _LOGGER.debug("Data fetched from resource: %s", value)
        if self.rest.headers is not None:
            # If the http request failed, headers will be None
            content_type = self.rest.headers.get("content-type")

            if content_type and (
                content_type.startswith("text/xml")
                or content_type.startswith("application/xml")
            ):
                try:
                    value = json.dumps(xmltodict.parse(value))
                    _LOGGER.debug("JSON converted from XML: %s", value)
                except ExpatError:
                    _LOGGER.warning(
                        "REST xml result could not be parsed and converted to JSON."
                    )
                    _LOGGER.debug("Erroneous XML: %s", value)

        if self._json_attrs:
            self._attributes = {}
            if value:
                try:
                    json_dict = json.loads(value)
                    if self._json_attrs_path is not None:
                        json_dict = jsonpath(json_dict, self._json_attrs_path)
                    # jsonpath will always store the result in json_dict[0]
                    # so the next line happens to work exactly as needed to
                    # find the result
                    if isinstance(json_dict, list):
                        json_dict = json_dict[0]
                    if isinstance(json_dict, dict):
                        attrs = {
                            k: json_dict[k] for k in self._json_attrs if k in json_dict
                        }
                        self._attributes = attrs
                    else:
                        _LOGGER.warning(
                            "JSON result was not a dictionary"
                            " or list with 0th element a dictionary"
                        )
                except ValueError:
                    _LOGGER.warning("REST result could not be parsed as JSON")
                    _LOGGER.debug("Erroneous JSON: %s", value)
            else:
                _LOGGER.warning("Empty reply found when expecting JSON data")
        if value is not None and self._value_template is not None:
            value = self._value_template.render_with_possible_json_value(value, None)

        self._state = value

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes


class RestData:
    """Class for handling the data retrieval."""

    def __init__(
        self, method, resource, auth, headers, data, verify_ssl, timeout=DEFAULT_TIMEOUT
    ):
        """Initialize the data object."""
        self._method = method
        self._resource = resource
        self._auth = auth
        self._headers = headers
        self._request_data = data
        self._verify_ssl = verify_ssl
        self._timeout = timeout
        self._http_session = Session()
        self.data = None
        self.headers = None

    def __del__(self):
        """Destroy the http session on destroy."""
        self._http_session.close()

    def set_url(self, url):
        """Set url."""
        self._resource = url

    def update(self):
        """Get the latest data from REST service with provided method."""
        _LOGGER.debug("Updating from %s", self._resource)
        try:
            response = self._http_session.request(
                self._method,
                self._resource,
                headers=self._headers,
                auth=self._auth,
                data=self._request_data,
                timeout=self._timeout,
                verify=self._verify_ssl,
            )
            self.data = response.text
            self.headers = response.headers
        except requests.exceptions.RequestException as ex:
            _LOGGER.error("Error fetching data: %s failed with %s", self._resource, ex)
            self.data = None
            self.headers = None
