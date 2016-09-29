"""
Currency exchange rate support that comes from Yahoo Finance.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.yahoo_finance/
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

ATTR_CHANGE = 'Change'
ATTR_OPEN = 'Open'
ATTR_PREV_CLOSE = 'Prev. Close'

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
                ATTR_CHANGE: self.data.price_change,
                ATTR_OPEN: self.data.price_open,
                ATTR_PREV_CLOSE: self.data.prev_close,
                'About': "Stock market information delivered by Yahoo!"
                         " Inc. are provided free of charge for use"
                         " by individuals and non-profit organizations"
                         " for personal, non-commercial uses."
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
    """Get data from Yahoo Finance."""

    def __init__(self, name, symbol):
        """Initialize the data object."""
        from yahoo_finance import Share

        self._name = name
        self._symbol = symbol
        self.state = None
        self.price_change = None
        self.price_open = None
        self.prev_close = None
        self.stock = Share(symbol)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data and updates the states."""
        self.stock.refresh()
        self.state = self.stock.get_price()
        self.price_change = self.stock.get_change()
        self.price_open = self.stock.get_open()
        self.prev_close = self.stock.get_prev_close()
