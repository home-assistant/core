"""
Details about crypto currencies from CoinMarketCap.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.coinmarketcap/
"""
import logging
from datetime import timedelta
import json
from urllib.error import HTTPError

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['coinmarketcap==2.0.1']

_LOGGER = logging.getLogger(__name__)

ATTR_24H_VOLUME_USD = '24h_volume_usd'
ATTR_AVAILABLE_SUPPLY = 'available_supply'
ATTR_MARKET_CAP = 'market_cap_usd'
ATTR_NAME = 'name'
ATTR_PERCENT_CHANGE_24H = 'percent_change_24h'
ATTR_PERCENT_CHANGE_7D = 'percent_change_7d'
ATTR_PRICE = 'price_usd'
ATTR_SYMBOL = 'symbol'
ATTR_TOTAL_SUPPLY = 'total_supply'

CONF_CURRENCY = 'currency'

DEFAULT_CURRENCY = 'bitcoin'

ICON = 'mdi:currency-usd'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_CURRENCY, default=DEFAULT_CURRENCY): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the CoinMarketCap sensor."""
    currency = config.get(CONF_CURRENCY)

    try:
        CoinMarketCapData(currency).update()
    except HTTPError:
        _LOGGER.warning('Currency "%s" is not available. Using "bitcoin"',
                        currency)
        currency = DEFAULT_CURRENCY

    add_devices([CoinMarketCapSensor(CoinMarketCapData(currency))])


# pylint: disable=too-few-public-methods
class CoinMarketCapSensor(Entity):
    """Representation of a CoinMarketCap sensor."""

    def __init__(self, data):
        """Initialize the sensor."""
        self.data = data
        self._ticker = None
        self._unit_of_measurement = 'USD'
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._ticker.get('name')

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._ticker.get('price_usd')

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_24H_VOLUME_USD: self._ticker.get('24h_volume_usd'),
            ATTR_AVAILABLE_SUPPLY: self._ticker.get('available_supply'),
            ATTR_MARKET_CAP: self._ticker.get('market_cap_usd'),
            ATTR_PERCENT_CHANGE_24H: self._ticker.get('percent_change_24h'),
            ATTR_PERCENT_CHANGE_7D: self._ticker.get('percent_change_7d'),
            ATTR_SYMBOL: self._ticker.get('symbol'),
            ATTR_TOTAL_SUPPLY: self._ticker.get('total_supply'),
        }

    # pylint: disable=too-many-branches
    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        self._ticker = json.loads(
            self.data.ticker.decode('utf-8').strip('\n '))[0]


class CoinMarketCapData(object):
    """Get the latest data and update the states."""

    def __init__(self, currency):
        """Initialize the data object."""
        self.currency = currency
        self.ticker = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from blockchain.info."""
        from coinmarketcap import Market

        self.ticker = Market().ticker(self.currency)
