"""The Coinbase integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from coinbase.rest import RESTClient
from coinbase.rest.rest_base import HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import Throttle

from .const import (
    ACCOUNT_IS_VAULT,
    API_ACCOUNT_AMOUNT,
    API_ACCOUNT_AVALIABLE,
    API_ACCOUNT_CURRENCY,
    API_ACCOUNT_HOLD,
    API_ACCOUNT_ID,
    API_ACCOUNT_NAME,
    API_ACCOUNT_VALUE,
    API_ACCOUNTS,
    API_DATA,
    API_RATES_CURRENCY,
    API_RESOURCE_TYPE,
    API_V3_ACCOUNT_ID,
    API_V3_TYPE_VAULT,
    CONF_EXCHANGE_BASE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

type CoinbaseConfigEntry = ConfigEntry[CoinbaseData]


async def async_setup_entry(hass: HomeAssistant, entry: CoinbaseConfigEntry) -> bool:
    """Set up Coinbase from a config entry."""

    instance = await hass.async_add_executor_job(create_and_update_instance, entry)
    entry.runtime_data = instance

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CoinbaseConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def create_and_update_instance(entry: CoinbaseConfigEntry) -> CoinbaseData:
    """Create and update a Coinbase Data instance."""

    # Check if user is using deprecated v2 API credentials
    if "organizations" not in entry.data[CONF_API_KEY]:
        # Trigger reauthentication to ask user for v3 credentials
        raise ConfigEntryAuthFailed(
            "Your Coinbase API key appears to be for the deprecated v2 API. "
            "Please reconfigure with a new API key created for the v3 API. "
            "Visit https://www.coinbase.com/developer-platform to create new credentials."
        )

    client = RESTClient(
        api_key=entry.data[CONF_API_KEY], api_secret=entry.data[CONF_API_TOKEN]
    )
    base_rate = entry.options.get(CONF_EXCHANGE_BASE, "USD")
    instance = CoinbaseData(client, base_rate)
    instance.update()
    return instance


def get_accounts(client):
    """Handle paginated accounts."""
    response = client.get_accounts()
    accounts = response[API_ACCOUNTS]
    while response["has_next"]:
        response = client.get_accounts(cursor=response["cursor"])
        accounts += response["accounts"]

    return [
        {
            API_ACCOUNT_ID: account[API_V3_ACCOUNT_ID],
            API_ACCOUNT_NAME: account[API_ACCOUNT_NAME],
            API_ACCOUNT_CURRENCY: account[API_ACCOUNT_CURRENCY],
            API_ACCOUNT_AMOUNT: (
                float(account[API_ACCOUNT_AVALIABLE][API_ACCOUNT_VALUE])
                + float(account[API_ACCOUNT_HOLD][API_ACCOUNT_VALUE])
            ),
            ACCOUNT_IS_VAULT: account[API_RESOURCE_TYPE] == API_V3_TYPE_VAULT,
        }
        for account in accounts
    ]


class CoinbaseData:
    """Get the latest data and update the states."""

    def __init__(self, client, exchange_base):
        """Init the coinbase data object."""

        self.client = client
        self.accounts = None
        self.exchange_base = exchange_base
        self.exchange_rates = None
        self.user_id = (
            "v3_" + client.get_portfolios()["portfolios"][0][API_V3_ACCOUNT_ID]
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from coinbase."""

        try:
            self.accounts = get_accounts(self.client)
            self.exchange_rates = self.client.get(
                "/v2/exchange-rates",
                params={API_RATES_CURRENCY: self.exchange_base},
            )[API_DATA]
        except HTTPError as coinbase_error:
            _LOGGER.error(
                "Authentication error connecting to coinbase: %s", coinbase_error
            )
