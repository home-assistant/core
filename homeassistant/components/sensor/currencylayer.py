"""Support for currencylayer.com exchange rates service."""
from datetime import timedelta
import logging
import requests
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.const import (CONF_API_KEY, CONF_NAME, CONF_PAYLOAD)

_RESOURCE = 'http://apilayer.net/api/live'
_LOGGER = logging.getLogger(__name__)
# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(hours=2)
CONF_BASE = 'base'
CONF_QUOTE = 'quote'
DEFAULT_BASE = 'USD'
DEFAULT_NAME = 'CurrencyLayer Sensor'
ICON = 'mdi:currency'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_QUOTE): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_BASE, default=DEFAULT_BASE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Currencylayer sensor."""
    payload = config.get(CONF_PAYLOAD)
    rest = CurrencylayerData(
        _RESOURCE,
        config.get(CONF_API_KEY),
        config.get(CONF_BASE, 'USD'),
        payload
    )
    response = requests.get(_RESOURCE, params={'source':
                                               config.get(CONF_BASE, 'USD'),
                                               'access_key':
                                               config.get(CONF_API_KEY),
                                               'format': 1}, timeout=10)
    sensors = []
    for variable in config['quote']:
        sensors.append(CurrencylayerSensor(rest, config.get(CONF_BASE, 'USD'),
                                           variable))
    if "error" in response.json():
        _LOGGER.error("Check your Currencylayer API")
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
        return str(self._base) + str(self._quote)

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update current conditions."""
        self.rest.update()
        value = self.rest.data
        if value is not None:
            self._state = round(value[str(self._base) + str(self._quote)], 4)


# pylint: disable=too-few-public-methods
class CurrencylayerData(object):
    """Get data from Currencylayer.org."""

    # pylint: disable=too-many-arguments
    def __init__(self, resource, api_key, base, data):
        """Initialize the data object."""
        self._resource = resource
        self._api_key = api_key
        self._base = base
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Currencylayer."""
        try:
            result = requests.get(self._resource, params={'source': self._base,
                                                          'access_key':
                                                          self._api_key,
                                                          'format': 1},
                                  timeout=10)
            if "error" in result.json():
                raise ValueError(result.json()["error"]["info"])
            else:
                self.data = result.json()['quotes']
                _LOGGER.debug("Currencylayer data updated: %s",
                              result.json()['timestamp'])
        except ValueError as err:
            _LOGGER.error("Check Currencylayer API %s", err.args)
            self.data = None
