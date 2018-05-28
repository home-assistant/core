"""
Details about crypto currencies from CoinMarketCap.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.coinmarketcap/
"""
import logging
from datetime import timedelta
from urllib.error import HTTPError

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_CURRENCY, CONF_DISPLAY_CURRENCY)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['coinmarketcap==4.2.1']

_LOGGER = logging.getLogger(__name__)

ATTR_24H_VOLUME = '24h_volume'
ATTR_AVAILABLE_SUPPLY = 'available_supply'
ATTR_MARKET_CAP = 'market_cap'
ATTR_PERCENT_CHANGE_24H = 'percent_change_24h'
ATTR_PERCENT_CHANGE_7D = 'percent_change_7d'
ATTR_PERCENT_CHANGE_1H = 'percent_change_1h'
ATTR_PRICE = 'price'
ATTR_SYMBOL = 'symbol'
ATTR_TOTAL_SUPPLY = 'total_supply'

CONF_ATTRIBUTION = "Data provided by CoinMarketCap"

DEFAULT_CURRENCY = 'bitcoin'
DEFAULT_DISPLAY_CURRENCY = 'USD'

ICON = 'mdi:currency-usd'

SCAN_INTERVAL = timedelta(minutes=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_CURRENCY, default=DEFAULT_CURRENCY): cv.string,
    vol.Optional(CONF_DISPLAY_CURRENCY, default=DEFAULT_DISPLAY_CURRENCY):
        cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the CoinMarketCap sensor."""
    currency = config.get(CONF_CURRENCY)
    display_currency = config.get(CONF_DISPLAY_CURRENCY).lower()

    try:
        CoinMarketCapData(currency, display_currency).update()
    except HTTPError:
        _LOGGER.warning("Currency %s or display currency %s is not available. "
                        "Using bitcoin and USD.", currency, display_currency)
        currency = DEFAULT_CURRENCY
        display_currency = DEFAULT_DISPLAY_CURRENCY

    add_devices([CoinMarketCapSensor(
        CoinMarketCapData(currency, display_currency))], True)


class CoinMarketCapSensor(Entity):
    """Representation of a CoinMarketCap sensor."""

    def __init__(self, data):
        """Initialize the sensor."""
        self.data = data
        self._ticker = None
        self._unit_of_measurement = self.data.display_currency.upper()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._ticker.get('name')

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(float(self._ticker.get(
            'price_{}'.format(self.data.display_currency))), 2)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_24H_VOLUME: self._ticker.get(
                '24h_volume_{}'.format(self.data.display_currency)),
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_AVAILABLE_SUPPLY: self._ticker.get('available_supply'),
            ATTR_MARKET_CAP: self._ticker.get(
                'market_cap_{}'.format(self.data.display_currency)),
            ATTR_PERCENT_CHANGE_24H: self._ticker.get('percent_change_24h'),
            ATTR_PERCENT_CHANGE_7D: self._ticker.get('percent_change_7d'),
            ATTR_PERCENT_CHANGE_1H: self._ticker.get('percent_change_1h'),
            ATTR_SYMBOL: self._ticker.get('symbol'),
            ATTR_TOTAL_SUPPLY: self._ticker.get('total_supply'),
        }

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        self._ticker = self.data.ticker[0]


class CoinMarketCapData(object):
    """Get the latest data and update the states."""

    def __init__(self, currency, display_currency):
        """Initialize the data object."""
        self.currency = currency
        self.display_currency = display_currency
        self.ticker = None

    def update(self):
        """Get the latest data from blockchain.info."""
        from coinmarketcap import Market
        self.ticker = Market().ticker(
            self.currency, limit=1, convert=self.display_currency)
