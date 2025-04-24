"""Test Redgtech switches."""

import pytest
from homeassistant.components.redgtech.switch import RedgtechSwitch
from unittest.mock import AsyncMock, patch, MagicMock
from homeassistant.core import HomeAssistant
from redgtech_api.api import RedgtechConnectionError
from homeassistant.exceptions import HomeAssistantError
from homeassistant.config_entries import ConfigEntryError

@pytest.fixture
def switch_data():
    """Return mock switch data."""
    device = MagicMock()
    device.id = "1234-5678"
    device.name = "Test Switch"
    device.state = False
    device.entity_id = "switch.test_switch"
    return device

@pytest.fixture
def access_token():
    return "test_access_token"

@pytest.fixture
def switch(hass: HomeAssistant, switch_data):
    """Return a RedgtechSwitch instance."""
    coordinator = MagicMock()
    coordinator.data = [switch_data]
    switch = RedgtechSwitch(coordinator, switch_data)
    switch.hass = hass
    switch.entity_id = switch_data.entity_id 
    return switch

@pytest.mark.asyncio
async def test_switch_initial_state(switch):
    """Test the initial state of the switch."""
    assert switch.name == "Test Switch"
    assert switch.is_on is False

@pytest.mark.asyncio
async def test_turn_on_switch(switch):
    """Test turning on the switch."""
    with patch.object(switch.coordinator, "set_device_state", new_callable=AsyncMock) as mock_set_state:
        await switch.async_turn_on()
        mock_set_state.assert_called_once_with("1234-5678", True)
        switch.device.state = True
        assert switch.device.state is True

@pytest.mark.asyncio
async def test_turn_off_switch(switch):
    """Test turning off the switch."""
    switch.device.state = True
    with patch.object(switch.coordinator, "set_device_state", new_callable=AsyncMock) as mock_set_state:
        await switch.async_turn_off()
        mock_set_state.assert_called_once_with("1234-5678", False)
        switch.device.state = False
        assert switch.device.state is False

@pytest.mark.asyncio
async def test_handle_connection_error(switch):
    """Test handling of connection errors when turning on the switch."""
    with patch.object(switch.coordinator, "set_device_state", new_callable=AsyncMock, side_effect=RedgtechConnectionError):
        with pytest.raises(Exception):
            await switch.async_turn_on()
