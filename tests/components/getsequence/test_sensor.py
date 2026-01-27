"""Tests for the Sequence sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_sensor_setup(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test sensor setup and initial state."""
    state = hass.states.get("sensor.sequence_account_savings_account_balance")
    assert state
    assert state.state == "5000.0"
    assert state.attributes["unit_of_measurement"] == "USD"


async def test_sensor_unavailable_when_balance_missing(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensor is unavailable when balance amount is missing."""
    mock_api_client = AsyncMock()
    mock_api_client.async_get_accounts.return_value = {
        "data": {
            "accounts": [
                {
                    "id": "acc_001",
                    "name": "Broken Account",
                    "balance": {},  # Missing amountInDollars
                }
            ]
        }
    }

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.coordinator.SequenceApiClient",
        return_value=mock_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.sequence_account_broken_account_balance")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_extra_state_attributes(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test sensor extra state attributes."""
    state = hass.states.get("sensor.sequence_account_savings_account_balance")
    assert state

    # Balance should NOT be in attributes
    assert "balance" not in state.attributes
    # Other account fields should be present
    assert state.attributes["id"] == "acc_001"
    assert state.attributes["name"] == "Savings Account"


async def test_sensor_with_balance_error_message(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensor includes balance error message in attributes."""
    mock_api_client = AsyncMock()
    mock_api_client.async_get_accounts.return_value = {
        "data": {
            "accounts": [
                {
                    "id": "acc_001",
                    "name": "Error Account",
                    "balance": {
                        "amountInDollars": 100.0,  # Valid balance
                        "displayMessage": "Account currently unavailable",
                    },
                }
            ]
        }
    }

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.coordinator.SequenceApiClient",
        return_value=mock_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.sequence_account_error_account_balance")
    assert state
    assert state.state == "100.0"
    assert "balance_error" in state.attributes
    assert state.attributes["balance_error"] == "Account currently unavailable"


async def test_sensor_unique_id(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor has correct unique ID."""
    entry_id = init_integration.entry_id
    entity_entry = entity_registry.async_get(
        "sensor.sequence_account_savings_account_balance"
    )
    assert entity_entry
    assert entity_entry.unique_id == f"{entry_id}_acc_001"


async def test_sensor_account_not_in_coordinator_data(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test sensor handles account removal from coordinator data."""
    # Get the coordinator from runtime_data
    coordinator = init_integration.runtime_data

    # Remove all accounts from coordinator data
    coordinator.async_set_updated_data([])
    await hass.async_block_till_done()

    # Sensor should now be unavailable
    state = hass.states.get("sensor.sequence_account_savings_account_balance")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_native_value_none_when_account_missing(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test native_value returns None when account data is missing."""
    coordinator = init_integration.runtime_data

    # Set coordinator data to empty list
    coordinator.async_set_updated_data([])
    await hass.async_block_till_done()

    state = hass.states.get("sensor.sequence_account_savings_account_balance")
    assert state
    # Should be unavailable, not showing a numeric value
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_extra_attributes_empty_when_account_missing(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test extra_state_attributes returns empty dict when account missing."""
    coordinator = init_integration.runtime_data

    # Set coordinator data to empty list
    coordinator.async_set_updated_data([])
    await hass.async_block_till_done()

    state = hass.states.get("sensor.sequence_account_savings_account_balance")
    assert state
    # Core attributes will still be there, but custom account attrs won't be
    assert "id" not in state.attributes
    assert "name" not in state.attributes
