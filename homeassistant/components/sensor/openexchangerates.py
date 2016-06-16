"""
Support for openexchangerates.org exchange rates service.
For more details about this platform, please refer to the documentation at (working on it).
"""
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.const import CONF_API_KEY
import requests
import logging
from datetime import timedelta

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
    rest = openexchangeratesData(_RESOURCE, config.get(CONF_API_KEY), 
           config.get(CONF_BASE,'USD'), config.get(CONF_QUOTE), payload)
    rest.update()
    add_devices([openexchangeratesSensor(rest, config.get(CONF_NAME,DEFAULT_NAME), 
                config.get(CONF_QUOTE))])

class openexchangeratesSensor(Entity):
    """Implementing the Openexchangerates sensor."""
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

class openexchangeratesData(object):
    """Get data from Openexchangerates.org."""
    def __init__(self, resource, api_key, base, quote, data):
        """Initialize the data object."""
        self._resource = resource
        self._api_key = api_key
        self._base = base
        self._quote = quote
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from openexchangerates."""
        try:
            result = requests.get(self._resource + '?base=' + 
                     self._base + '&app_id=' + self._api_key)
            self.data = result.json()['rates']
            _LOGGER.debug(result.json()['timestamp'])
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to host/endpoint: %s", self._resource)
            self.data = None
