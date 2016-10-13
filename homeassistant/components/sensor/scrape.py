"""
Support for getting data from websites with scraping.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.scrape/
"""
import logging

import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.sensor.rest import RestData
from homeassistant.const import (
    CONF_NAME, CONF_RESOURCE, CONF_UNIT_OF_MEASUREMENT, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['beautifulsoup4==4.5.1']

_LOGGER = logging.getLogger(__name__)

CONF_SELECT = 'select'
CONF_ELEMENT = 'element'
CONF_BEFORE = 'before'
CONF_AFTER = 'after'

DEFAULT_NAME = 'Web scrape'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_SELECT): cv.string,
    vol.Optional(CONF_ELEMENT, default=0): cv.positive_int,
    vol.Optional(CONF_BEFORE, default=0): cv.positive_int,
    vol.Optional(CONF_AFTER, default=99999): cv.positive_int,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
})


# pylint: disable=too-many-locals
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Web scrape sensor."""
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)
    method = 'GET'
    payload = auth = headers = None
    verify_ssl = True
    select = config.get(CONF_SELECT)
    element = config.get(CONF_ELEMENT)
    before = config.get(CONF_BEFORE)
    after = config.get(CONF_AFTER)
    unit = config.get(CONF_UNIT_OF_MEASUREMENT)

    rest = RestData(method, resource, auth, headers, payload, verify_ssl)
    rest.update()

    if rest.data is None:
        _LOGGER.error("Unable to fetch data from %s", resource)
        return False

    add_devices([
        ScrapeSensor(rest, name, select, element, before, after, unit)
    ])


# pylint: disable=too-many-instance-attributes
class ScrapeSensor(Entity):
    """Representation of a web scrape sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, rest, name, select, element, before, after, unit):
        """Initialize a web scrape sensor."""
        self.rest = rest
        self._name = name
        self._state = STATE_UNKNOWN
        self._select = select
        self._element = element
        self._before = before
        self._after = after
        self._unit_of_measurement = unit
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
        """Get the latest data from the source and updates the state."""
        self.rest.update()

        from bs4 import BeautifulSoup

        raw_data = BeautifulSoup(self.rest.data, 'html.parser')
        _LOGGER.debug(raw_data)
        data = raw_data.select(self._select)
        _LOGGER.error(data)

        try:
            self._state = data[self._element].text[self._before:self._after]
        except TypeError:
            _LOGGER.warning("Unable to extract a value")
            self._state = STATE_UNKNOWN
