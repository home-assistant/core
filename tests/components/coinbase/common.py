"""Collection of helpers."""

from unittest.mock import patch

from homeassistant.components.coinbase.const import (
    CONF_CURRENCIES,
    CONF_EXCHANGE_RATES,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN

from .const import (
    GOOD_CURRENCY,
    GOOD_CURRENCY_2,
    GOOD_EXCHNAGE_RATE,
    GOOD_EXCHNAGE_RATE_2,
)

from tests.common import MockConfigEntry


def mock_get_current_user():
    """Return a simplified mock user."""
    return {
        "id": "123456-abcdef",
        "name": "Test User",
    }


def mock_get_accounts():
    """Return a simplified list of mock accounts."""
    return {
        "data": [
            {
                "balance": {"amount": "0.00001", "currency": GOOD_CURRENCY},
                "currency": "BTC",
                "id": "123456789",
                "name": "BTC Wallet",
                "native_balance": {"amount": "100.12", "currency": GOOD_CURRENCY},
            },
            {
                "balance": {"amount": "9.90", "currency": GOOD_CURRENCY_2},
                "currency": "USD",
                "id": "987654321",
                "name": "USD Wallet",
                "native_balance": {"amount": "9.90", "currency": GOOD_CURRENCY_2},
            },
        ]
    }


def mock_get_exchange_rates():
    """Return a heavily reduced mock list of exchange rates for testing."""
    return {
        "currency": "USD",
        "rates": {GOOD_EXCHNAGE_RATE_2: "0.109", GOOD_EXCHNAGE_RATE: "0.00002"},
    }


async def init_mock_coinbase(hass):
    """Init Coinbase integration for testing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="abcde12345",
        title="Test User",
        data={CONF_API_KEY: "123456", CONF_API_TOKEN: "AbCDeF"},
        options={
            CONF_CURRENCIES: [],
            CONF_EXCHANGE_RATES: [],
        },
    )
    config_entry.add_to_hass(hass)

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
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry
