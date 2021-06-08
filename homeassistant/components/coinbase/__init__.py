"""The Coinbase integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from coinbase.wallet.client import Client
from coinbase.wallet.error import AuthenticationError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
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
    {
        DOMAIN: vol.Schema(
            cv.deprecated(CONF_API_KEY),
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


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Coinbase component."""
    if DOMAIN not in config:
        return True
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Coinbase from a config entry."""

    # Do a one-time handle of options from YAML
    if entry.source == SOURCE_IMPORT and not entry.options:
        import_options: dict[str, list[str]] = {
            CONF_CURRENCIES: [],
            CONF_EXCHANGE_RATES: [],
        }
        if CONF_CURRENCIES in entry.data:
            import_options[CONF_CURRENCIES] = entry.data[CONF_CURRENCIES]
        if CONF_EXCHANGE_RATES in entry.data:
            import_options[CONF_EXCHANGE_RATES] = entry.data[CONF_EXCHANGE_RATES]

        hass.config_entries.async_update_entry(entry, options=import_options)

    client = await hass.async_add_executor_job(
        Client,
        entry.data[CONF_API_KEY],
        entry.data[CONF_API_TOKEN],
    )
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = await hass.async_add_executor_job(
        CoinbaseData, client
    )
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
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
