"""
Support for Coinbase.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/coinbase/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.util import Throttle

REQUIREMENTS = ['coinbase==2.1.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'coinbase'

CONF_API_SECRET = 'api_secret'
CONF_EXCHANGE_CURRENCIES = 'exchange_rate_currencies'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

DATA_COINBASE = 'coinbase_cache'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_API_SECRET): cv.string,
        vol.Optional(CONF_EXCHANGE_CURRENCIES, default=[]):
            vol.All(cv.ensure_list, [cv.string])
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Coinbase component.

    Will automatically setup sensors to support
    wallets discovered on the network.
    """
    api_key = config[DOMAIN].get(CONF_API_KEY)
    api_secret = config[DOMAIN].get(CONF_API_SECRET)
    exchange_currencies = config[DOMAIN].get(CONF_EXCHANGE_CURRENCIES)

    hass.data[DATA_COINBASE] = coinbase_data = CoinbaseData(
        api_key, api_secret)

    if not hasattr(coinbase_data, 'accounts'):
        return False
    for account in coinbase_data.accounts.data:
        load_platform(hass, 'sensor', DOMAIN, {'account': account}, config)
    for currency in exchange_currencies:
        if currency not in coinbase_data.exchange_rates.rates:
            _LOGGER.warning("Currency %s not found", currency)
            continue
        native = coinbase_data.exchange_rates.currency
        load_platform(hass,
                      'sensor',
                      DOMAIN,
                      {'native_currency': native,
                       'exchange_currency': currency},
                      config)

    return True


class CoinbaseData(object):
    """Get the latest data and update the states."""

    def __init__(self, api_key, api_secret):
        """Init the coinbase data object."""
        from coinbase.wallet.client import Client
        self.client = Client(api_key, api_secret)
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from coinbase."""
        from coinbase.wallet.error import AuthenticationError
        try:
            self.accounts = self.client.get_accounts()
            self.exchange_rates = self.client.get_exchange_rates()
        except AuthenticationError as coinbase_error:
            _LOGGER.error("Authentication error connecting"
                          " to coinbase: %s", coinbase_error)
