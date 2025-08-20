"""Test the Coinbase integration."""

from unittest.mock import patch

import pytest

from homeassistant.components.coinbase import create_and_update_instance
from homeassistant.components.coinbase.const import (
    API_TYPE_VAULT,
    CONF_CURRENCIES,
    CONF_EXCHANGE_RATES,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er

from .common import (
    init_mock_coinbase,
    mock_get_exchange_rates,
    mock_get_portfolios,
    mocked_get_accounts_v3,
)
from .const import (
    GOOD_CURRENCY,
    GOOD_CURRENCY_2,
    GOOD_EXCHANGE_RATE,
    GOOD_EXCHANGE_RATE_2,
)


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    with (
        patch(
            "coinbase.rest.RESTClient.get_portfolios",
            return_value=mock_get_portfolios(),
        ),
        patch(
            "coinbase.rest.RESTClient.get_accounts",
            new=mocked_get_accounts_v3,
        ),
        patch(
            "coinbase.rest.RESTClient.get",
            return_value={"data": {"rates": {}}},
        ),
    ):
        entry = await init_mock_coinbase(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_option_updates(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test handling option updates."""

    with (
        patch(
            "coinbase.rest.RESTClient.get_portfolios",
            return_value=mock_get_portfolios(),
        ),
        patch("coinbase.rest.RESTClient.get_accounts", new=mocked_get_accounts_v3),
        patch(
            "coinbase.rest.RESTClient.get",
            return_value={"data": mock_get_exchange_rates()},
        ),
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

        entities = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
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

        entities = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
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


async def test_ignore_vaults_wallets(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test vaults are ignored in wallet sensors."""

    with (
        patch(
            "coinbase.rest.RESTClient.get_portfolios",
            return_value=mock_get_portfolios(),
        ),
        patch("coinbase.rest.RESTClient.get_accounts", new=mocked_get_accounts_v3),
        patch(
            "coinbase.rest.RESTClient.get",
            return_value={"data": mock_get_exchange_rates()},
        ),
    ):
        config_entry = await init_mock_coinbase(hass, currencies=[GOOD_CURRENCY])
        await hass.async_block_till_done()

        entities = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        assert len(entities) == 1
        entity = entities[0]
        assert API_TYPE_VAULT not in entity.original_name.lower()


async def test_v2_api_credentials_trigger_reauth(hass: HomeAssistant) -> None:
    """Test that v2 API credentials trigger a reauth flow."""

    config_entry_data = {
        CONF_API_KEY: "v2_api_key_legacy_format",
        CONF_API_TOKEN: "v2_api_secret",
    }

    class MockConfigEntry:
        def __init__(self, data) -> None:
            self.data = data
            self.options = {}

    entry = MockConfigEntry(config_entry_data)

    with pytest.raises(ConfigEntryAuthFailed) as exc_info:
        create_and_update_instance(entry)

    assert "deprecated v2 API" in str(exc_info.value)


async def test_v3_api_credentials_work(hass: HomeAssistant) -> None:
    """Test that v3 API credentials with 'organizations' don't trigger reauth."""

    config_entry_data = {
        CONF_API_KEY: "organizations_v3_api_key",
        CONF_API_TOKEN: "v3_api_secret",
    }

    class MockConfigEntry:
        def __init__(self, data) -> None:
            self.data = data
            self.options = {}

    entry = MockConfigEntry(config_entry_data)

    with (
        patch(
            "coinbase.rest.RESTClient.get_portfolios",
            return_value=mock_get_portfolios(),
        ),
        patch("coinbase.rest.RESTClient.get_accounts", new=mocked_get_accounts_v3),
        patch(
            "coinbase.rest.RESTClient.get",
            return_value={"data": mock_get_exchange_rates()},
        ),
    ):
        instance = create_and_update_instance(entry)
        assert instance is not None
