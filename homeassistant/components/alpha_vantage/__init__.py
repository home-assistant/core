"""Support for stock market information from Alpha Vantage."""
import logging
from datetime import timedelta
import re

import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_CURRENCY, CONF_NAME, \
    CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval
from homeassistant.components.sensor import DOMAIN as SENSOR

REQUIREMENTS = ['alpha_vantage==2.1.0']

DOMAIN = 'alpha_vantage'
STOCK_DATA_UPDATED = '{}_stock_data_updated'.format(DOMAIN)
FOREX_DATA_UPDATED = '{}_forex_data_updated'.format(DOMAIN)

_LOGGER = logging.getLogger(__name__)

CONF_FOREIGN_EXCHANGE = 'foreign_exchange'
CONF_FROM = 'from'
CONF_SYMBOL = 'symbol'
CONF_SYMBOLS = 'symbols'
CONF_TO = 'to'

DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

SYMBOL_SCHEMA = vol.Schema({
    vol.Required(CONF_SYMBOL): cv.string,
    vol.Optional(CONF_CURRENCY): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})

CURRENCY_SCHEMA = vol.Schema({
    vol.Required(CONF_FROM): cv.string,
    vol.Required(CONF_TO): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(
        vol.Schema({
            vol.Required(CONF_API_KEY): cv.string,
            vol.Optional(CONF_FOREIGN_EXCHANGE, default=[]):
                vol.All(cv.ensure_list, [CURRENCY_SCHEMA]),
            vol.Optional(CONF_SYMBOLS, default=[]):
                vol.All(cv.ensure_list, [SYMBOL_SCHEMA]),
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
                vol.All(cv.time_period, cv.positive_timedelta),
        }),
        cv.has_at_least_one_key(CONF_FOREIGN_EXCHANGE, CONF_SYMBOLS)
    )
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Alpha Vantage component."""
    conf = config[DOMAIN]
    data = hass.data[DOMAIN] = AlphaVantageData(
        hass,
        conf[CONF_API_KEY],
        [symbol[CONF_SYMBOL] for symbol in conf[CONF_SYMBOLS]],
        conf[CONF_FOREIGN_EXCHANGE]
    )
    data.update()

    track_time_interval(
        hass, data.update, conf[CONF_SCAN_INTERVAL]
    )

    load_platform(
        hass,
        SENSOR,
        DOMAIN,
        {
            CONF_SYMBOLS: conf[CONF_SYMBOLS],
            CONF_FOREIGN_EXCHANGE: conf[CONF_FOREIGN_EXCHANGE]
        },
        config
    )

    return True


class AlphaVantageData:
    """Container for AlphaVantage stock market data."""

    def __init__(self, hass, api_key, symbols, conversions):
        """Initialize Data."""
        from alpha_vantage.timeseries import TimeSeries
        from alpha_vantage.foreignexchange import ForeignExchange

        self._hass = hass
        self._regex = re.compile('(\d+\. )(.+)')
        self._timeseries = TimeSeries(key=api_key)
        self._forex = ForeignExchange(key=api_key)
        self._symbols = symbols
        self._conversions = conversions
        self._stock_quotes = {symbol: {} for symbol in symbols}
        self._forex_quotes = {
            (conversion[CONF_FROM], conversion[CONF_TO]): None
            for conversion in conversions
        }

    @property
    def stock_quotes(self):
        return self._stock_quotes

    @property
    def forex_quotes(self):
        return self._forex_quotes

    def update(self, now=None):
        """Update Data."""
        self._update_stock_tickers()
        self._update_currency_data()

    def _update_stock_tickers(self):
        """Update cached data for tracked stock tickers."""
        if len(self._symbols) == 0:
            return
        try:
            quotes, _ = self._timeseries.get_batch_stock_quotes(self._symbols)
            self._stock_quotes = {
                quote['1. symbol']: {
                    self._regex.match(k).group(2): v
                    for k, v in quote.items()
                    if k != '1. symbol'
                }
                for quote in quotes
            }
            dispatcher_send(self._hass, STOCK_DATA_UPDATED)
        except ValueError:
            _LOGGER.error(
                'API key is not valid or symbols %s not known',
                ', '.join(self._symbols)
            )

    def _update_currency_data(self):
        """Update cached data for tracked currency conversions."""
        if len(self._conversions) == 0:
            return
        for conversion in self._conversions:
            key = (conversion[CONF_FROM], conversion[CONF_TO])
            try:
                values, _ = self._forex.get_currency_exchange_rate(
                    from_currency=key[0],
                    to_currency=key[1]
                )
                self._forex_quotes[key] = {
                    self._regex.match(k).group(2): v
                    for k, v in values.items()
                }
                dispatcher_send(self._hass, FOREX_DATA_UPDATED)
            except ValueError:
                _LOGGER.error(
                    'API key is not valid or cannot convert'
                    'currencies %s, %s ',
                    key[0],
                    key[1]
                )
