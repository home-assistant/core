"""Test the Coinbase diagnostics."""

from unittest.mock import patch

from aiohttp import ClientSession

from .common import (
    init_mock_coinbase,
    mock_get_current_user,
    mock_get_exchange_rates,
    mocked_get_accounts,
)

from tests.components.coinbase.const import (
    MOCK_ACCOUNTS_RESPONSE_REDACTED,
    MOCK_ENTRY_REDACTED,
)
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, hass_client: ClientSession):
    """Test we handle a and redact a diagnostics request."""

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

        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

        # Remove the ID to match the constant
        result["entry"].pop("entry_id")

        assert result == {
            "entry": MOCK_ENTRY_REDACTED,
            "accounts": MOCK_ACCOUNTS_RESPONSE_REDACTED,
        }
