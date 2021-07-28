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
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

from .const import (
    API_ACCOUNT_ID,
    API_ACCOUNTS_DATA,
    CONF_CURRENCIES,
    CONF_EXCHANGE_BASE,
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Coinbase from a config entry."""

    instance = await hass.async_add_executor_job(create_and_update_instance, entry)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = instance

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def create_and_update_instance(entry: ConfigEntry) -> CoinbaseData:
    """Create and update a Coinbase Data instance."""
    client = Client(entry.data[CONF_API_KEY], entry.data[CONF_API_TOKEN])
    base_rate = entry.options.get(CONF_EXCHANGE_BASE, "USD")
    instance = CoinbaseData(client, base_rate)
    instance.update()
    return instance


async def update_listener(hass, config_entry):
    """Handle options update."""

    await hass.config_entries.async_reload(config_entry.entry_id)

    registry = entity_registry.async_get(hass)
    entities = entity_registry.async_entries_for_config_entry(
        registry, config_entry.entry_id
    )

    # Remove orphaned entities
    for entity in entities:
        currency = entity.unique_id.split("-")[-1]
        if "xe" in entity.unique_id and currency not in config_entry.options.get(
            CONF_EXCHANGE_RATES
        ):
            registry.async_remove(entity.entity_id)
        elif "wallet" in entity.unique_id and currency not in config_entry.options.get(
            CONF_CURRENCIES
        ):
            registry.async_remove(entity.entity_id)


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

    def __init__(self, client, exchange_base):
        """Init the coinbase data object."""

        self.client = client
        self.accounts = None
        self.exchange_base = exchange_base
        self.exchange_rates = None
        self.user_id = self.client.get_current_user()[API_ACCOUNT_ID]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from coinbase."""

        try:
            self.accounts = get_accounts(self.client)
            self.exchange_rates = self.client.get_exchange_rates(
                currency=self.exchange_base
            )
        except AuthenticationError as coinbase_error:
            _LOGGER.error(
                "Authentication error connecting to coinbase: %s", coinbase_error
            )
