"""Tests for the Redgtech switch platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.redgtech.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from redgtech_api.api import RedgtechAuthError, RedgtechConnectionError
from tests.common import MockConfigEntry


@pytest.fixture
def mock_redgtech_api():
    """Mock the Redgtech API."""
    api = AsyncMock()
    api.login = AsyncMock(return_value="mock_access_token")
    api.get_data = AsyncMock(return_value={
        "boards": [
            {
                "endpointId": "switch_001",
                "friendlyName": "Living Room Switch",
                "value": False
            },
            {
                "endpointId": "switch_002", 
                "friendlyName": "Kitchen Switch",
                "value": True
            }
        ]
    })
    api.set_switch_state = AsyncMock()
    return api


@pytest.fixture
def config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "password123"
        },
        entry_id="test_entry",
    )


@pytest.fixture
async def setup_redgtech_integration(hass: HomeAssistant, config_entry, mock_redgtech_api):
    """Set up the Redgtech integration with mocked API."""
    with patch("homeassistant.components.redgtech.coordinator.RedgtechAPI", return_value=mock_redgtech_api):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    
    return mock_redgtech_api


async def test_switch_setup_and_initial_state(hass: HomeAssistant, setup_redgtech_integration):
    """Test switch setup and initial states."""
    mock_api = setup_redgtech_integration
    
    # Verify API was called during setup
    mock_api.login.assert_called_with("test@example.com", "password123")
    mock_api.get_data.assert_called()
    
    # Check that switches were created with correct states
    living_room_state = hass.states.get("switch.living_room_switch")
    kitchen_state = hass.states.get("switch.kitchen_switch")
    
    assert living_room_state is not None
    assert living_room_state.state == STATE_OFF
    assert living_room_state.name == "Living Room Switch"
    
    assert kitchen_state is not None
    assert kitchen_state.state == STATE_ON
    assert kitchen_state.name == "Kitchen Switch"


async def test_switch_turn_on(hass: HomeAssistant, setup_redgtech_integration):
    """Test turning a switch on."""
    mock_api = setup_redgtech_integration
    
    # Turn on the living room switch
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.living_room_switch"},
        blocking=True,
    )
    
    # Verify API was called to set switch state
    mock_api.set_switch_state.assert_called_with("switch_001", True, "mock_access_token")


async def test_switch_turn_off(hass: HomeAssistant, setup_redgtech_integration):
    """Test turning a switch off."""
    mock_api = setup_redgtech_integration
    
    # Turn off the kitchen switch
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.kitchen_switch"},
        blocking=True,
    )
    
    # Verify API was called to set switch state
    mock_api.set_switch_state.assert_called_with("switch_002", False, "mock_access_token")


async def test_switch_toggle(hass: HomeAssistant, setup_redgtech_integration):
    """Test toggling a switch."""
    mock_api = setup_redgtech_integration
    
    # Toggle the living room switch (currently off, should turn on)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "toggle",
        {"entity_id": "switch.living_room_switch"},
        blocking=True,
    )
    
    # Verify API was called to set switch state to on
    mock_api.set_switch_state.assert_called_with("switch_001", True, "mock_access_token")


async def test_switch_connection_error(hass: HomeAssistant, setup_redgtech_integration):
    """Test handling connection errors when controlling switches."""
    mock_api = setup_redgtech_integration
    mock_api.set_switch_state.side_effect = RedgtechConnectionError("Connection failed")
    
    with pytest.raises(HomeAssistantError, match="Connection error"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_on",
            {"entity_id": "switch.living_room_switch"},
            blocking=True,
        )


async def test_switch_auth_error_with_retry(hass: HomeAssistant, setup_redgtech_integration):
    """Test handling auth errors with token renewal."""
    mock_api = setup_redgtech_integration
    
    # First call fails with auth error, second succeeds
    mock_api.set_switch_state.side_effect = [
        RedgtechAuthError("Auth failed"),
        None  # Success on retry
    ]
    
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.living_room_switch"},
        blocking=True,
    )
    
    # Verify login was called again for token renewal
    assert mock_api.login.call_count >= 2
    # Verify set_switch_state was called twice (initial + retry)
    assert mock_api.set_switch_state.call_count == 2


async def test_coordinator_data_update_success(hass: HomeAssistant, setup_redgtech_integration):
    """Test successful data update through coordinator."""
    mock_api = setup_redgtech_integration
    
    # Get the coordinator from the config entry
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    coordinator = config_entries[0].runtime_data
    
    # Update mock data
    mock_api.get_data.return_value = {
        "boards": [
            {
                "endpointId": "switch_001",
                "friendlyName": "Living Room Switch",
                "value": True  # Changed to True
            }
        ]
    }
    
    # Trigger coordinator update
    await coordinator.async_refresh()
    
    # Verify the data was updated successfully
    assert coordinator.last_exception is None
    assert len(coordinator.data) == 1
    assert coordinator.data[0].unique_id == "switch_001"
    assert coordinator.data[0].state == STATE_ON


async def test_coordinator_connection_error_during_update(hass: HomeAssistant, setup_redgtech_integration):
    """Test coordinator handling connection errors during data updates."""
    mock_api = setup_redgtech_integration
    mock_api.get_data.side_effect = RedgtechConnectionError("Connection failed")
    
    # Get the coordinator
    config_entries = hass.config_entries.async_entries(DOMAIN)
    coordinator = config_entries[0].runtime_data
    
    # Trigger update - coordinator will handle the exception internally
    await coordinator.async_refresh()
    
    # Verify the coordinator is in an error state
    assert coordinator.last_exception is not None
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert "Failed to connect to Redgtech API" in str(coordinator.last_exception)


async def test_coordinator_auth_error_with_token_renewal(hass: HomeAssistant, setup_redgtech_integration):
    """Test coordinator handling auth errors with token renewal."""
    mock_api = setup_redgtech_integration
    
    # First call fails with auth error, second succeeds after token renewal
    mock_api.get_data.side_effect = [
        RedgtechAuthError("Auth failed"),
        {
            "boards": [
                {
                    "endpointId": "switch_001",
                    "friendlyName": "Living Room Switch",
                    "value": True
                }
            ]
        }
    ]
    
    # Get the coordinator
    config_entries = hass.config_entries.async_entries(DOMAIN)
    coordinator = config_entries[0].runtime_data
    
    # Trigger update
    await coordinator.async_refresh()
    
    # Verify token renewal was attempted
    assert mock_api.login.call_count >= 2
    # Verify data was eventually retrieved successfully
    assert coordinator.last_exception is None
    assert len(coordinator.data) == 1
    assert coordinator.data[0].unique_id == "switch_001"