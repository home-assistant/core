"""
Currency exchange rate support that comes from Yahoo Finance.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.yahoo_finance/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['yahoo-finance==1.4.0']

_LOGGER = logging.getLogger(__name__)

ATTR_CHANGE = 'Change'
ATTR_OPEN = 'open'
ATTR_PREV_CLOSE = 'prev_close'

CONF_ATTRIBUTION = "Stock market information provided by Yahoo! Inc."
CONF_SYMBOLS = 'symbols'

DEFAULT_NAME = 'Yahoo Stock'
DEFAULT_SYMBOL = 'YHOO'

ICON = 'mdi:currency-usd'

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SYMBOLS, default=[DEFAULT_SYMBOL]):
        vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Yahoo Finance sensor."""
    from yahoo_finance import Share

    symbols = config.get(CONF_SYMBOLS)

    dev = []
    for symbol in symbols:
        if Share(symbol).get_price() is None:
            _LOGGER.warning("Symbol %s unknown", symbol)
            break
        data = YahooFinanceData(symbol)
        dev.append(YahooFinanceSensor(data, symbol))

    add_entities(dev, True)


class YahooFinanceSensor(Entity):
    """Representation of a Yahoo Finance sensor."""

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
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._state is not None:
            return {
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                ATTR_CHANGE: self.data.price_change,
                ATTR_OPEN: self.data.price_open,
                ATTR_PREV_CLOSE: self.data.prev_close,
            }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating sensor %s - %s", self._name, self._state)
        self.data.update()
        self._state = self.data.state


class YahooFinanceData:
    """Get data from Yahoo Finance."""

    def __init__(self, symbol):
        """Initialize the data object."""
        from yahoo_finance import Share

        self._symbol = symbol
        self.state = None
        self.price_change = None
        self.price_open = None
        self.prev_close = None
        self.stock = Share(self._symbol)

    def update(self):
        """Get the latest data and updates the states."""
        self.stock.refresh()
        self.state = self.stock.get_price()
        self.price_change = self.stock.get_change()
        self.price_open = self.stock.get_open()
        self.prev_close = self.stock.get_prev_close()
