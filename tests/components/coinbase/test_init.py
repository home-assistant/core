"""Test the Coinbase integration."""
from unittest.mock import patch

from homeassistant.components.coinbase.const import (
    CONF_CURRENCIES,
    CONF_EXCHANGE_RATES,
    CONF_YAML_API_TOKEN,
    DOMAIN,
)
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    SOURCE_IMPORT,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.setup import async_setup_component

from .common import (
    init_mock_coinbase,
    mock_get_accounts,
    mock_get_current_user,
    mock_get_exchange_rates,
)
from .const import (
    GOOD_CURRENCY,
    GOOD_CURRENCY_2,
    GOOD_EXCHNAGE_RATE,
    GOOD_EXCHNAGE_RATE_2,
)


async def test_setup(hass):
    """Test setting up from configuration.yaml."""
    conf = {
        DOMAIN: {
            CONF_API_KEY: "123456",
            CONF_YAML_API_TOKEN: "AbCDeF",
            CONF_CURRENCIES: [GOOD_CURRENCY, GOOD_CURRENCY_2],
            CONF_EXCHANGE_RATES: [GOOD_EXCHNAGE_RATE, GOOD_EXCHNAGE_RATE_2],
        }
    }
    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value=mock_get_current_user(),
    ), patch(
        "coinbase.wallet.client.Client.get_accounts",
        return_value=mock_get_accounts(),
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value=mock_get_exchange_rates(),
    ):
        assert await async_setup_component(hass, DOMAIN, conf)
        config_entries = hass.config_entries.async_entries(DOMAIN)
        assert len(config_entries) == 1
        assert config_entries[0].title == "Test User"
        assert config_entries[0].source == SOURCE_IMPORT
        assert config_entries[0].options == {
            CONF_CURRENCIES: [GOOD_CURRENCY, GOOD_CURRENCY_2],
            CONF_EXCHANGE_RATES: [GOOD_EXCHNAGE_RATE, GOOD_EXCHNAGE_RATE_2],
        }


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    entry = await init_mock_coinbase(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
