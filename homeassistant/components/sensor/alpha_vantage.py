"""
Stock market information from Alpha Vantage.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.alpha_vantage/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_API_KEY
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['alpha_vantage==1.3.6']

_LOGGER = logging.getLogger(__name__)

ATTR_CLOSE = 'close'
ATTR_HIGH = 'high'
ATTR_OPEN = 'open'
ATTR_LOW = 'low'
ATTR_VOLUME = 'volume'

CONF_ATTRIBUTION = "Stock market information provided by Alpha Vantage."
CONF_SYMBOLS = 'symbols'

DEFAULT_SYMBOL = 'GOOGL'

ICON = 'mdi:currency-usd'

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_SYMBOLS, default=[DEFAULT_SYMBOL]):
        vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Alpha Vantage sensor."""
    from alpha_vantage.timeseries import TimeSeries

    api_key = config.get(CONF_API_KEY)
    symbols = config.get(CONF_SYMBOLS)

    timeserie = TimeSeries(key=api_key)

    dev = []
    for symbol in symbols:
        try:
            data = AlphaVantageData(timeserie, symbol)
            data.update()
        except ValueError:
            _LOGGER.error("API Key is not valid or symbol not known")
            return False
        dev.append(AlphaVantageSensor(data, symbol))

    add_devices(dev)


class AlphaVantageSensor(Entity):
    """Representation of a Alpha Vantage sensor."""

    def __init__(self, data, symbol):
        """Initialize the sensor."""
        self._name = symbol
        self.data = data
        self._symbol = symbol
        self._state = None
        self._unit_of_measurement = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._symbol

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.data.values['1. open']

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.data is not None:
            return {
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                ATTR_CLOSE: self.data.values['4. close'],
                ATTR_HIGH: self.data.values['2. high'],
                ATTR_LOW: self.data.values['3. low'],
                ATTR_VOLUME: self.data.values['5. volume'],
            }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()


class AlphaVantageData(object):
    """Get data from Alpha Vantage."""

    def __init__(self, timeserie, symbol):
        """Initialize the data object."""
        self._symbol = symbol
        self._timeserie = timeserie
        self.values = None

    def update(self):
        """Get the latest data and updates the states."""
        all_values, _ = self._timeserie.get_intraday(self._symbol)
        self.values = next(iter(all_values.values()))
