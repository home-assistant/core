"""Test the Rotarex coordinator."""

from unittest.mock import AsyncMock

import pytest
from rotarex_dimes_srg_api import InvalidAuth

from homeassistant.components.rotarex.coordinator import RotarexDataUpdateCoordinator
from homeassistant.components.rotarex.models import RotarexTank
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_data_structure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test coordinator returns properly structured data."""
    mock_config_entry.add_to_hass(hass)
    
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    coordinator = mock_config_entry.runtime_data

    # Verify data is a dict indexed by GUID
    assert isinstance(coordinator.data, dict)
    assert "tank1-guid" in coordinator.data
    assert "tank2-guid" in coordinator.data

    # Verify data is properly typed
    tank1 = coordinator.data["tank1-guid"]
    assert isinstance(tank1, RotarexTank)
    assert tank1.guid == "tank1-guid"
    assert tank1.name == "Tank 1"
    assert len(tank1.synch_datas) == 2
    assert tank1.synch_datas[0].level == 75.5
    assert tank1.synch_datas[0].battery == 85.0


async def test_coordinator_auth_failure_on_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test coordinator handles auth failure during setup."""
    mock_rotarex_api.login.side_effect = InvalidAuth("Invalid credentials")
    
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Config entry should be in setup_retry state due to auth failure
    assert mock_config_entry.state.recoverable


async def test_coordinator_reauth_on_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test coordinator re-authenticates when token expires."""
    mock_config_entry.add_to_hass(hass)
    
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    coordinator = mock_config_entry.runtime_data

    # Simulate token expiration on fetch
    mock_rotarex_api.fetch_tanks.side_effect = [
        InvalidAuth("Token expired"),
        [  # After re-login, successful fetch
            {
                "Guid": "tank1-guid",
                "Name": "Tank 1",
                "SynchDatas": [
                    {
                        "SynchDate": "2024-01-03T12:00:00Z",
                        "Level": 65.0,
                        "Battery": 75.0,
                    }
                ],
            }
        ],
    ]

    mock_rotarex_api.login.reset_mock()
    await coordinator.async_refresh()

    # Verify login was called for re-auth
    assert mock_rotarex_api.login.call_count == 1
    assert coordinator.data["tank1-guid"].synch_datas[0].level == 65.0


async def test_coordinator_reauth_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test coordinator handles failed re-authentication."""
    mock_config_entry.add_to_hass(hass)
    
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    coordinator = mock_config_entry.runtime_data
    
    # Initial state should be successful
    assert coordinator.last_update_success is True

    # Simulate token expiration and failed re-login
    mock_rotarex_api.fetch_tanks.side_effect = InvalidAuth("Token expired")
    mock_rotarex_api.login.side_effect = InvalidAuth("Invalid credentials")

    await coordinator.async_refresh()
    
    # Coordinator should mark update as failed but not raise exception
    assert coordinator.last_update_success is False
