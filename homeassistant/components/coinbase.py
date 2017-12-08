"""
Support for Coinbase.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/coinbase/
"""
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_API_KEY
from homeassistant.util import Throttle
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['coinbase==2.0.6']

DOMAIN = 'coinbase'

CONF_API_SECRET = 'api_secret'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

DATA_COINBASE = 'coinbase_cache'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_API_SECRET): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Coinbase component.

    Will automatically setup sensors to support
    wallets discovered on the network.
    """
    api_key = config[DOMAIN].get(CONF_API_KEY)
    api_secret = config[DOMAIN].get(CONF_API_SECRET)

    if DATA_COINBASE not in hass.data:
        hass.data[DATA_COINBASE] = CoinbaseData(api_key, api_secret)

    for account in hass.data[DATA_COINBASE].accounts['data']:
        load_platform(hass, 'sensor', DOMAIN, {'account': account})

    return True


class CoinbaseData(object):
    """Get the latest data and update the states."""

    def __init__(self, api_key, api_secret):
        """Init the coinbase data object."""
        from coinbase.wallet.client import Client
        self.client = Client(api_key, api_secret)
        self.accounts = self.client.get_accounts()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from coinbase."""
        self.accounts = self.client.get_accounts()
