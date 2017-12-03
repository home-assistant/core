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

    timeseries = TimeSeries(key=api_key)

    dev = []
    for symbol in symbols:
        try:
            timeseries.get_intraday(symbol)
        except ValueError:
            _LOGGER.error(
                "API Key is not valid or symbol '%s' not known", symbol)
            return
        dev.append(AlphaVantageSensor(timeseries, symbol))

    add_devices(dev, True)


class AlphaVantageSensor(Entity):
    """Representation of a Alpha Vantage sensor."""

    def __init__(self, timeseries, symbol):
        """Initialize the sensor."""
        self._name = symbol
        self._timeseries = timeseries
        self._symbol = symbol
        self.values = None
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
        return self.values['1. open']

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.values is not None:
            return {
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                ATTR_CLOSE: self.values['4. close'],
                ATTR_HIGH: self.values['2. high'],
                ATTR_LOW: self.values['3. low'],
                ATTR_VOLUME: self.values['5. volume'],
            }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and updates the states."""
        all_values, _ = self._timeseries.get_intraday(self._symbol)
        self.values = next(iter(all_values.values()))
