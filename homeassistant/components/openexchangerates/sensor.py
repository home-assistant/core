"""Support for openexchangerates.org exchange rates service."""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_BASE,
    CONF_NAME,
    CONF_QUOTE,
    HTTP_OK,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
_RESOURCE = "https://openexchangerates.org/api/latest.json"

ATTRIBUTION = "Data provided by openexchangerates.org"

DEFAULT_BASE = "USD"
DEFAULT_NAME = "Exchange Rate Sensor"

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_QUOTE): cv.string,
        vol.Optional(CONF_BASE, default=DEFAULT_BASE): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Open Exchange Rates sensor."""
    name = config.get(CONF_NAME)
    api_key = config.get(CONF_API_KEY)
    base = config.get(CONF_BASE)
    quote = config.get(CONF_QUOTE)

    parameters = {"base": base, "app_id": api_key}

    rest = OpenexchangeratesData(_RESOURCE, parameters, quote)
    response = requests.get(_RESOURCE, params=parameters, timeout=10)

    if response.status_code != HTTP_OK:
        _LOGGER.error("Check your OpenExchangeRates API key")
        return False

    rest.update()
    add_entities([OpenexchangeratesSensor(rest, name, quote)], True)


class OpenexchangeratesSensor(SensorEntity):
    """Representation of an Open Exchange Rates sensor."""

    def __init__(self, rest, name, quote):
        """Initialize the sensor."""
        self.rest = rest
        self._name = name
        self._quote = quote
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return other attributes of the sensor."""
        attr = self.rest.data
        attr[ATTR_ATTRIBUTION] = ATTRIBUTION

        return attr

    def update(self):
        """Update current conditions."""
        self.rest.update()
        value = self.rest.data
        self._state = round(value[str(self._quote)], 4)


class OpenexchangeratesData:
    """Get data from Openexchangerates.org."""

    def __init__(self, resource, parameters, quote):
        """Initialize the data object."""
        self._resource = resource
        self._parameters = parameters
        self._quote = quote
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from openexchangerates.org."""
        try:
            result = requests.get(self._resource, params=self._parameters, timeout=10)
            self.data = result.json()["rates"]
        except requests.exceptions.HTTPError:
            _LOGGER.error("Check the Openexchangerates API key")
            self.data = None
            return False
