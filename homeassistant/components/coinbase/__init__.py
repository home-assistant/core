"""The Coinbase integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from coinbase.wallet.client import Client
from coinbase.wallet.error import AuthenticationError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

from .const import (
    API_ACCOUNT_ID,
    API_ACCOUNTS_DATA,
    CONF_CURRENCIES,
    CONF_EXCHANGE_RATES,
    CONF_YAML_API_TOKEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)


CONFIG_SCHEMA = vol.Schema(
    cv.deprecated(DOMAIN),
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_YAML_API_TOKEN): cv.string,
                vol.Optional(CONF_CURRENCIES): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional(CONF_EXCHANGE_RATES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            },
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Coinbase component.

    Will automatically setup sensors to support
    wallets discovered on the network.
    """
    api_key = config[DOMAIN][CONF_API_KEY]
    api_secret = config[DOMAIN][CONF_API_SECRET]
    account_currencies = config[DOMAIN].get(CONF_ACCOUNT_CURRENCIES)
    exchange_currencies = config[DOMAIN][CONF_EXCHANGE_CURRENCIES]

    hass.data[DATA_COINBASE] = coinbase_data = CoinbaseData(api_key, api_secret)

    if not hasattr(coinbase_data, "accounts"):
        return False
    if account_currencies is not None:
        provided_accounts = {}
        for account in coinbase_data.accounts:
            provided_accounts[account.currency] = account
        for user_account in account_currencies:
            if user_account in provided_accounts:
                load_platform(
                    hass,
                    "sensor",
                    DOMAIN,
                    {"account": provided_accounts[user_account]},
                    config,
                )
            else:
                _LOGGER.warning(
                    "Account %s not found, please check your API settings on Coinbase",
                    user_account,
                )
    for currency in exchange_currencies:
        if currency not in coinbase_data.exchange_rates.rates:
            _LOGGER.warning("Currency %s not found", currency)
            continue
        native = coinbase_data.exchange_rates.currency
        load_platform(
            hass,
            "sensor",
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Coinbase from a config entry."""

    client = await hass.async_add_executor_job(
        Client,
        entry.data[CONF_API_KEY],
        entry.data[CONF_API_TOKEN],
    )

    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = await hass.async_add_executor_job(
        CoinbaseData, client
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def get_accounts(client):
    """Handle paginated accounts."""
    response = client.get_accounts()
    accounts = response[API_ACCOUNTS_DATA]
    next_starting_after = response.pagination.next_starting_after

    while next_starting_after:
        response = client.get_accounts(starting_after=next_starting_after)
        accounts += response[API_ACCOUNTS_DATA]
        next_starting_after = response.pagination.next_starting_after

    return accounts


class CoinbaseData:
    """Get the latest data and update the states."""

    def __init__(self, client):
        """Init the coinbase data object."""

        self.client = client
        self.accounts = get_accounts(self.client)
        self.exchange_rates = self.client.get_exchange_rates()
        self.user_id = self.client.get_current_user()[API_ACCOUNT_ID]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from coinbase."""

        try:
            self.accounts = get_accounts(self.client)
            self.exchange_rates = self.client.get_exchange_rates()
        except AuthenticationError as coinbase_error:
            _LOGGER.error(
                "Authentication error connecting to coinbase: %s", coinbase_error
            )
