"""Test the Coinbase diagnostics."""

from unittest.mock import patch

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from .common import (
    init_mock_coinbase,
    mock_get_exchange_rates,
    mock_get_portfolios,
    mocked_get_accounts_v3,
)


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test we handle a and redact a diagnostics request."""

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

        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

        assert result == snapshot(exclude=props("created_at", "modified_at"))
