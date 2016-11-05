"""
Support for currencylayer.com exchange rates service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.currencylayer/
"""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, CONF_BASE, CONF_QUOTE, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://apilayer.net/api/live'

CONF_ATTRIBUTION = "Data provided by currencylayer.com"

DEFAULT_BASE = 'USD'
DEFAULT_NAME = 'CurrencyLayer Sensor'

ICON = 'mdi:currency'

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_QUOTE): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_BASE, default=DEFAULT_BASE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Currencylayer sensor."""
    base = config.get(CONF_BASE)
    api_key = config.get(CONF_API_KEY)
    parameters = {
        'source': base,
        'access_key': api_key,
        'format': 1,
    }

    rest = CurrencylayerData(_RESOURCE, parameters)

    response = requests.get(_RESOURCE, params=parameters, timeout=10)
    sensors = []
    for variable in config['quote']:
        sensors.append(CurrencylayerSensor(rest, base, variable))
    if 'error' in response.json():
        return False
    else:
        add_devices(sensors)
        rest.update()


class CurrencylayerSensor(Entity):
    """Implementing the Currencylayer sensor."""

    def __init__(self, rest, base, quote):
        """Initialize the sensor."""
        self.rest = rest
        self._quote = quote
        self._base = base
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._base, self._quote)

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }

    def update(self):
        """Update current date."""
        self.rest.update()
        value = self.rest.data
        if value is not None:
            self._state = round(
                value['{}{}'.format(self._base, self._quote)], 4)


class CurrencylayerData(object):
    """Get data from Currencylayer.org."""

    def __init__(self, resource, parameters):
        """Initialize the data object."""
        self._resource = resource
        self._parameters = parameters
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Currencylayer."""
        try:
            result = requests.get(
                self._resource, params=self._parameters, timeout=10)
            if 'error' in result.json():
                raise ValueError(result.json()['error']['info'])
            else:
                self.data = result.json()['quotes']
                _LOGGER.debug("Currencylayer data updated: %s",
                              result.json()['timestamp'])
        except ValueError as err:
            _LOGGER.error("Check Currencylayer API %s", err.args)
            self.data = None
