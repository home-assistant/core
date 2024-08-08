"""The Coinbase integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from coinbase.rest import RESTClient
from coinbase.rest.rest_base import HTTPError
from coinbase.wallet.client import Client as LegacyClient
from coinbase.wallet.error import AuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import Throttle

from .const import (
    ACCOUNT_IS_VAULT,
    API_ACCOUNT_AMOUNT,
    API_ACCOUNT_AVALIABLE,
    API_ACCOUNT_BALANCE,
    API_ACCOUNT_CURRENCY,
    API_ACCOUNT_CURRENCY_CODE,
    API_ACCOUNT_HOLD,
    API_ACCOUNT_ID,
    API_ACCOUNT_NAME,
    API_ACCOUNT_VALUE,
    API_ACCOUNTS,
    API_DATA,
    API_RATES_CURRENCY,
    API_RESOURCE_TYPE,
    API_TYPE_VAULT,
    API_V3_ACCOUNT_ID,
    API_V3_TYPE_VAULT,
    CONF_CURRENCIES,
    CONF_EXCHANGE_BASE,
    CONF_EXCHANGE_RATES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Coinbase from a config entry."""

    instance = await hass.async_add_executor_job(create_and_update_instance, entry)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = instance

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def create_and_update_instance(entry: ConfigEntry) -> CoinbaseData:
    """Create and update a Coinbase Data instance."""
    if "organizations" not in entry.data[CONF_API_KEY]:
        client = LegacyClient(entry.data[CONF_API_KEY], entry.data[CONF_API_TOKEN])
        version = "v2"
    else:
        client = RESTClient(
            api_key=entry.data[CONF_API_KEY], api_secret=entry.data[CONF_API_TOKEN]
        )
        version = "v3"
    base_rate = entry.options.get(CONF_EXCHANGE_BASE, "USD")
    instance = CoinbaseData(client, base_rate, version)
    instance.update()
    return instance


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""

    await hass.config_entries.async_reload(config_entry.entry_id)

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, config_entry.entry_id)

    # Remove orphaned entities
    for entity in entities:
        currency = entity.unique_id.split("-")[-1]
        if (
            "xe" in entity.unique_id
            and currency not in config_entry.options.get(CONF_EXCHANGE_RATES, [])
            or "wallet" in entity.unique_id
            and currency not in config_entry.options.get(CONF_CURRENCIES, [])
        ):
            registry.async_remove(entity.entity_id)


def get_accounts(client, version):
    """Handle paginated accounts."""
    response = client.get_accounts()
    if version == "v2":
        accounts = response[API_DATA]
        next_starting_after = response.pagination.next_starting_after

        while next_starting_after:
            response = client.get_accounts(starting_after=next_starting_after)
            accounts += response[API_DATA]
            next_starting_after = response.pagination.next_starting_after

        return [
            {
                API_ACCOUNT_ID: account[API_ACCOUNT_ID],
                API_ACCOUNT_NAME: account[API_ACCOUNT_NAME],
                API_ACCOUNT_CURRENCY: account[API_ACCOUNT_CURRENCY][
                    API_ACCOUNT_CURRENCY_CODE
                ],
                API_ACCOUNT_AMOUNT: account[API_ACCOUNT_BALANCE][API_ACCOUNT_AMOUNT],
                ACCOUNT_IS_VAULT: account[API_RESOURCE_TYPE] == API_TYPE_VAULT,
            }
            for account in accounts
        ]

    accounts = response[API_ACCOUNTS]
    while response["has_next"]:
        response = client.get_accounts(cursor=response["cursor"])
        accounts += response["accounts"]

    return [
        {
            API_ACCOUNT_ID: account[API_V3_ACCOUNT_ID],
            API_ACCOUNT_NAME: account[API_ACCOUNT_NAME],
            API_ACCOUNT_CURRENCY: account[API_ACCOUNT_CURRENCY],
            API_ACCOUNT_AMOUNT: account[API_ACCOUNT_AVALIABLE][API_ACCOUNT_VALUE]
            + account[API_ACCOUNT_HOLD][API_ACCOUNT_VALUE],
            ACCOUNT_IS_VAULT: account[API_RESOURCE_TYPE] == API_V3_TYPE_VAULT,
        }
        for account in accounts
    ]


class CoinbaseData:
    """Get the latest data and update the states."""

    def __init__(self, client, exchange_base, version):
        """Init the coinbase data object."""

        self.client = client
        self.accounts = None
        self.exchange_base = exchange_base
        self.exchange_rates = None
        if version == "v2":
            self.user_id = self.client.get_current_user()[API_ACCOUNT_ID]
        else:
            self.user_id = (
                "v3_" + client.get_portfolios()["portfolios"][0][API_V3_ACCOUNT_ID]
            )
        self.api_version = version

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from coinbase."""

        try:
            self.accounts = get_accounts(self.client, self.api_version)
            if self.api_version == "v2":
                self.exchange_rates = self.client.get_exchange_rates(
                    currency=self.exchange_base
                )
            else:
                self.exchange_rates = self.client.get(
                    "/v2/exchange-rates",
                    params={API_RATES_CURRENCY: self.exchange_base},
                )[API_DATA]
        except (AuthenticationError, HTTPError) as coinbase_error:
            _LOGGER.error(
                "Authentication error connecting to coinbase: %s", coinbase_error
            )
