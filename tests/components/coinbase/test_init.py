"""Test the Coinbase integration."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.coinbase.const import (
    API_TYPE_VAULT,
    CONF_CURRENCIES,
    CONF_EXCHANGE_RATES,
    CONF_YAML_API_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from .common import (
    init_mock_coinbase,
    mock_get_current_user,
    mock_get_exchange_rates,
    mocked_get_accounts,
)
from .const import (
    GOOD_CURRENCY,
    GOOD_CURRENCY_2,
    GOOD_EXCHANGE_RATE,
    GOOD_EXCHANGE_RATE_2,
)


async def test_setup(hass):
    """Test setting up from configuration.yaml."""
    conf = {
        DOMAIN: {
            CONF_API_KEY: "123456",
            CONF_YAML_API_TOKEN: "AbCDeF",
            CONF_CURRENCIES: [GOOD_CURRENCY, GOOD_CURRENCY_2],
            CONF_EXCHANGE_RATES: [GOOD_EXCHANGE_RATE, GOOD_EXCHANGE_RATE_2],
        }
    }
    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value=mock_get_current_user(),
    ), patch(
        "coinbase.wallet.client.Client.get_accounts",
        new=mocked_get_accounts,
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value=mock_get_exchange_rates(),
    ):
        assert await async_setup_component(hass, DOMAIN, conf)
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        assert entries[0].title == "Test User"
        assert entries[0].source == config_entries.SOURCE_IMPORT
        assert entries[0].options == {
            CONF_CURRENCIES: [GOOD_CURRENCY, GOOD_CURRENCY_2],
            CONF_EXCHANGE_RATES: [GOOD_EXCHANGE_RATE, GOOD_EXCHANGE_RATE_2],
        }


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value=mock_get_current_user(),
    ), patch(
        "coinbase.wallet.client.Client.get_accounts",
        new=mocked_get_accounts,
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value=mock_get_exchange_rates(),
    ):
        entry = await init_mock_coinbase(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == config_entries.ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_option_updates(hass: HomeAssistant):
    """Test handling option updates."""

    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value=mock_get_current_user(),
    ), patch(
        "coinbase.wallet.client.Client.get_accounts", new=mocked_get_accounts
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value=mock_get_exchange_rates(),
    ):
        config_entry = await init_mock_coinbase(hass)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_CURRENCIES: [GOOD_CURRENCY, GOOD_CURRENCY_2],
                CONF_EXCHANGE_RATES: [GOOD_EXCHANGE_RATE, GOOD_EXCHANGE_RATE_2],
            },
        )
        await hass.async_block_till_done()

        registry = entity_registry.async_get(hass)
        entities = entity_registry.async_entries_for_config_entry(
            registry, config_entry.entry_id
        )
        assert len(entities) == 4
        currencies = [
            entity.unique_id.split("-")[-1]
            for entity in entities
            if "wallet" in entity.unique_id
        ]

        rates = [
            entity.unique_id.split("-")[-1]
            for entity in entities
            if "xe" in entity.unique_id
        ]

        assert currencies == [GOOD_CURRENCY, GOOD_CURRENCY_2]
        assert rates == [GOOD_EXCHANGE_RATE, GOOD_EXCHANGE_RATE_2]

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_CURRENCIES: [GOOD_CURRENCY],
                CONF_EXCHANGE_RATES: [GOOD_EXCHANGE_RATE],
            },
        )
        await hass.async_block_till_done()

        registry = entity_registry.async_get(hass)
        entities = entity_registry.async_entries_for_config_entry(
            registry, config_entry.entry_id
        )
        assert len(entities) == 2
        currencies = [
            entity.unique_id.split("-")[-1]
            for entity in entities
            if "wallet" in entity.unique_id
        ]

        rates = [
            entity.unique_id.split("-")[-1]
            for entity in entities
            if "xe" in entity.unique_id
        ]

        assert currencies == [GOOD_CURRENCY]
        assert rates == [GOOD_EXCHANGE_RATE]


async def test_ignore_vaults_wallets(hass: HomeAssistant):
    """Test vaults are ignored in wallet sensors."""

    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value=mock_get_current_user(),
    ), patch(
        "coinbase.wallet.client.Client.get_accounts", new=mocked_get_accounts
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value=mock_get_exchange_rates(),
    ):
        config_entry = await init_mock_coinbase(hass, currencies=[GOOD_CURRENCY])
        await hass.async_block_till_done()

        registry = entity_registry.async_get(hass)
        entities = entity_registry.async_entries_for_config_entry(
            registry, config_entry.entry_id
        )
        assert len(entities) == 1
        entity = entities[0]
        assert API_TYPE_VAULT not in entity.original_name.lower()
