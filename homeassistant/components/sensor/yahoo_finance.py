"""
Currency exchange rate support that comes from Yahoo Finance.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.yahoo-finance/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['yahoo-finance==1.2.1']

_LOGGER = logging.getLogger(__name__)

CONF_SYMBOL = 'symbol'
DEFAULT_SYMBOL = 'YHOO'
DEFAULT_NAME = 'Yahoo Stock'

ICON = 'mdi:currency-usd'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

STATE_ATTR_PRICE_SALES = 'Price/Sales (ttm)'
STATE_ATTR_CHANGE = 'Change'
STATE_ATTR_OPEN = 'Open'
STATE_ATTR_PREV_CLOSE = 'Prev. Close'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SYMBOL, default=DEFAULT_SYMBOL): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Yahoo Finance sensor."""

    name = config.get(CONF_NAME)
    symbol = config.get(CONF_SYMBOL)

    data = YahooFinanceData(name, symbol)
    add_devices([YahooFinanceSensor(name, data, symbol)])


# pylint: disable=too-few-public-methods
class YahooFinanceSensor(Entity):
    """Representation of a Yahoo Finance sensor."""

    def __init__(self, name, data, symbol):
        """Initialize the sensor."""
        self._name = name
        self.data = data
        self._symbol = symbol
        self._state = None
        self._unit_of_measurement = None
        self.update()

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
                STATE_ATTR_CHANGE: self.data.stock.get_change(),
                STATE_ATTR_PRICE_SALES: self.data.stock.get_price_sales(),
                STATE_ATTR_OPEN: self.data.stock.get_open(),
                STATE_ATTR_PREV_CLOSE: self.data.stock.get_prev_close(),
            }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug('Updating sensor %s - %s', self._name, self._state)
        self.data.update()
        self._state = self.data.state

class YahooFinanceData(object):
    """Get data from Yahoo Finance"""

    def __init__(self, name, symbol):
        """Initialize the data object."""
        from yahoo_finance import Share

        self._name = name
        self._symbol = symbol
        self.state = None
        self.stock = Share(symbol)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data and updates the states."""
        self.stock.refresh()
        self.state = self.stock.get_price()
