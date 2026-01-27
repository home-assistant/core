"""Tests for the Sequence coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant

from .const import DOMAIN

from tests.common import MockConfigEntry


async def test_coordinator_initialization(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test coordinator initialization."""
    coordinator = init_integration.runtime_data

    assert coordinator.name == DOMAIN
    assert coordinator.update_interval.total_seconds() == 300  # 5 minutes


async def test_coordinator_update_success(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test successful data update."""
    coordinator = init_integration.runtime_data

    assert coordinator.data is not None
    assert len(coordinator.data) == 1
    assert coordinator.data[0]["id"] == "acc_001"
    assert coordinator.data[0]["name"] == "Savings Account"
    assert coordinator.data[0]["balance"]["amountInDollars"] == 5000.00


async def test_coordinator_empty_accounts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client_empty_accounts,
) -> None:
    """Test coordinator handles empty accounts list."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.coordinator.SequenceApiClient",
        return_value=mock_api_client_empty_accounts,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data == []


async def test_coordinator_malformed_response_missing_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator handles malformed response with missing fields."""
    mock_api_client = AsyncMock()
    # Return account data with missing balance
    mock_api_client.async_get_accounts.return_value = {
        "data": {"accounts": [{"id": "acc_001", "name": "Test"}]}
    }

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.coordinator.SequenceApiClient",
        return_value=mock_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Should not crash, coordinator should handle gracefully
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data is not None
