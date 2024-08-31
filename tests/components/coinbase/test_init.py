"""Test the Coinbase integration."""

from unittest.mock import patch

from homeassistant.components.coinbase.const import (
    API_TYPE_VAULT,
    CONF_CURRENCIES,
    CONF_EXCHANGE_RATES,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    with (
        patch(
            "coinbase.wallet.client.Client.get_current_user",
            return_value=mock_get_current_user(),
        ),
        patch(
            "coinbase.wallet.client.Client.get_accounts",
            new=mocked_get_accounts,
        ),
        patch(
            "coinbase.wallet.client.Client.get_exchange_rates",
            return_value=mock_get_exchange_rates(),
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
            "coinbase.wallet.client.Client.get_current_user",
            return_value=mock_get_current_user(),
        ),
        patch("coinbase.wallet.client.Client.get_accounts", new=mocked_get_accounts),
        patch(
            "coinbase.wallet.client.Client.get_exchange_rates",
            return_value=mock_get_exchange_rates(),
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
            "coinbase.wallet.client.Client.get_current_user",
            return_value=mock_get_current_user(),
        ),
        patch("coinbase.wallet.client.Client.get_accounts", new=mocked_get_accounts),
        patch(
            "coinbase.wallet.client.Client.get_exchange_rates",
            return_value=mock_get_exchange_rates(),
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
