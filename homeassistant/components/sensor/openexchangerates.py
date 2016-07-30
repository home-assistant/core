"""
Support for openexchangerates.org exchange rates service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.openexchangerates/
"""
from datetime import timedelta
import logging
import requests
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.const import CONF_API_KEY

_RESOURCE = 'https://openexchangerates.org/api/latest.json'
_LOGGER = logging.getLogger(__name__)
# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=100)
CONF_BASE = 'base'
CONF_QUOTE = 'quote'
CONF_NAME = 'name'
DEFAULT_NAME = 'Exchange Rate Sensor'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Openexchangerates sensor."""
    payload = config.get('payload', None)
    rest = OpenexchangeratesData(
        _RESOURCE,
        config.get(CONF_API_KEY),
        config.get(CONF_BASE, 'USD'),
        config.get(CONF_QUOTE),
        payload
    )
    response = requests.get(_RESOURCE, params={'base': config.get(CONF_BASE,
                                                                  'USD'),
                                               'app_id':
                                               config.get(CONF_API_KEY)},
                            timeout=10)
    if response.status_code != 200:
        _LOGGER.error("Check your OpenExchangeRates API")
        return False
    rest.update()
    add_devices([OpenexchangeratesSensor(rest, config.get(CONF_NAME,
                                                          DEFAULT_NAME),
                                         config.get(CONF_QUOTE))])


class OpenexchangeratesSensor(Entity):
    """Representation of an Openexchangerates sensor."""

    def __init__(self, rest, name, quote):
        """Initialize the sensor."""
        self.rest = rest
        self._name = name
        self._quote = quote
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return other attributes of the sensor."""
        return self.rest.data

    def update(self):
        """Update current conditions."""
        self.rest.update()
        value = self.rest.data
        self._state = round(value[str(self._quote)], 4)


# pylint: disable=too-few-public-methods
class OpenexchangeratesData(object):
    """Get data from Openexchangerates.org."""

    # pylint: disable=too-many-arguments
    def __init__(self, resource, api_key, base, quote, data):
        """Initialize the data object."""
        self._resource = resource
        self._api_key = api_key
        self._base = base
        self._quote = quote
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from openexchangerates.org."""
        try:
            result = requests.get(self._resource, params={'base': self._base,
                                                          'app_id':
                                                          self._api_key},
                                  timeout=10)
            self.data = result.json()['rates']
        except requests.exceptions.HTTPError:
            _LOGGER.error("Check Openexchangerates API Key")
            self.data = None
            return False
