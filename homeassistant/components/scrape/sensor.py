"""Support for getting data from websites with scraping."""
import logging

from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant.components.rest.sensor import RestData
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RESOURCE,
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

CONF_ATTR = "attribute"
CONF_SELECT = "select"
CONF_INDEX = "index"

DEFAULT_NAME = "Web scrape"
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCE): cv.string,
        vol.Required(CONF_SELECT): cv.string,
        vol.Optional(CONF_ATTR): cv.string,
        vol.Optional(CONF_INDEX, default=0): cv.positive_int,
        vol.Optional(CONF_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Web scrape sensor."""
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)
    method = "GET"
    payload = None
    headers = config.get(CONF_HEADERS)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    select = config.get(CONF_SELECT)
    attr = config.get(CONF_ATTR)
    index = config.get(CONF_INDEX)
    unit = config.get(CONF_UNIT_OF_MEASUREMENT)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
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
        raise PlatformNotReady

    add_entities(
        [ScrapeSensor(rest, name, select, attr, index, value_template, unit)], True
    )


class ScrapeSensor(Entity):
    """Representation of a web scrape sensor."""

    def __init__(self, rest, name, select, attr, index, value_template, unit):
        """Initialize a web scrape sensor."""
        self.rest = rest
        self._name = name
        self._state = None
        self._select = select
        self._attr = attr
        self._index = index
        self._value_template = value_template
        self._unit_of_measurement = unit

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
        """Get the latest data from the source and updates the state."""
        self.rest.update()
        if self.rest.data is None:
            _LOGGER.error("Unable to retrieve data")
            return

        raw_data = BeautifulSoup(self.rest.data, "html.parser")
        _LOGGER.debug(raw_data)

        try:
            if self._attr is not None:
                value = raw_data.select(self._select)[self._index][self._attr]
            else:
                tag = raw_data.select(self._select)[self._index]
                if tag.name in ("style", "script", "template"):
                    value = tag.string
                else:
                    value = tag.text
            _LOGGER.debug(value)
        except IndexError:
            _LOGGER.error("Unable to extract data from HTML")
            return

        if self._value_template is not None:
            self._state = self._value_template.render_with_possible_json_value(
                value, None
            )
        else:
            self._state = value
