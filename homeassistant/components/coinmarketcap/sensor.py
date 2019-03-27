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
    ATTR_ATTRIBUTION, CONF_DISPLAY_CURRENCY)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['coinmarketcap==5.0.3']

_LOGGER = logging.getLogger(__name__)

ATTR_VOLUME_24H = 'volume_24h'
ATTR_AVAILABLE_SUPPLY = 'available_supply'
ATTR_CIRCULATING_SUPPLY = 'circulating_supply'
ATTR_MARKET_CAP = 'market_cap'
ATTR_PERCENT_CHANGE_24H = 'percent_change_24h'
ATTR_PERCENT_CHANGE_7D = 'percent_change_7d'
ATTR_PERCENT_CHANGE_1H = 'percent_change_1h'
ATTR_PRICE = 'price'
ATTR_RANK = 'rank'
ATTR_SYMBOL = 'symbol'
ATTR_TOTAL_SUPPLY = 'total_supply'

ATTRIBUTION = "Data provided by CoinMarketCap"

CONF_CURRENCY_ID = 'currency_id'
CONF_DISPLAY_CURRENCY_DECIMALS = 'display_currency_decimals'

DEFAULT_CURRENCY_ID = 1
DEFAULT_DISPLAY_CURRENCY = 'USD'
DEFAULT_DISPLAY_CURRENCY_DECIMALS = 2

ICON = 'mdi:currency-usd'

SCAN_INTERVAL = timedelta(minutes=15)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_CURRENCY_ID, default=DEFAULT_CURRENCY_ID):
        cv.positive_int,
    vol.Optional(CONF_DISPLAY_CURRENCY, default=DEFAULT_DISPLAY_CURRENCY):
        cv.string,
    vol.Optional(CONF_DISPLAY_CURRENCY_DECIMALS,
                 default=DEFAULT_DISPLAY_CURRENCY_DECIMALS):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the CoinMarketCap sensor."""
    currency_id = config.get(CONF_CURRENCY_ID)
    display_currency = config.get(CONF_DISPLAY_CURRENCY).upper()
    display_currency_decimals = config.get(CONF_DISPLAY_CURRENCY_DECIMALS)

    try:
        CoinMarketCapData(currency_id, display_currency).update()
    except HTTPError:
        _LOGGER.warning("Currency ID %s or display currency %s "
                        "is not available. Using 1 (bitcoin) "
                        "and USD.", currency_id, display_currency)
        currency_id = DEFAULT_CURRENCY_ID
        display_currency = DEFAULT_DISPLAY_CURRENCY

    add_entities([CoinMarketCapSensor(
        CoinMarketCapData(
            currency_id, display_currency), display_currency_decimals)], True)


class CoinMarketCapSensor(Entity):
    """Representation of a CoinMarketCap sensor."""

    def __init__(self, data, display_currency_decimals):
        """Initialize the sensor."""
        self.data = data
        self.display_currency_decimals = display_currency_decimals
        self._ticker = None
        self._unit_of_measurement = self.data.display_currency

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._ticker.get('name')

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(float(
            self._ticker.get('quotes').get(self.data.display_currency)
            .get('price')), self.display_currency_decimals)

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
            ATTR_VOLUME_24H:
                self._ticker.get('quotes').get(self.data.display_currency)
                .get('volume_24h'),
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_CIRCULATING_SUPPLY: self._ticker.get('circulating_supply'),
            ATTR_MARKET_CAP:
                self._ticker.get('quotes').get(self.data.display_currency)
                .get('market_cap'),
            ATTR_PERCENT_CHANGE_24H:
                self._ticker.get('quotes').get(self.data.display_currency)
                .get('percent_change_24h'),
            ATTR_PERCENT_CHANGE_7D:
                self._ticker.get('quotes').get(self.data.display_currency)
                .get('percent_change_7d'),
            ATTR_PERCENT_CHANGE_1H:
                self._ticker.get('quotes').get(self.data.display_currency)
                .get('percent_change_1h'),
            ATTR_RANK: self._ticker.get('rank'),
            ATTR_SYMBOL: self._ticker.get('symbol'),
            ATTR_TOTAL_SUPPLY: self._ticker.get('total_supply'),
        }

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        self._ticker = self.data.ticker.get('data')


class CoinMarketCapData:
    """Get the latest data and update the states."""

    def __init__(self, currency_id, display_currency):
        """Initialize the data object."""
        self.currency_id = currency_id
        self.display_currency = display_currency
        self.ticker = None

    def update(self):
        """Get the latest data from coinmarketcap.com."""
        from coinmarketcap import Market
        self.ticker = Market().ticker(
            self.currency_id, convert=self.display_currency)
