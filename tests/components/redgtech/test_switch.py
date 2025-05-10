"""Test Redgtech switches."""

import pytest
from homeassistant.components.redgtech.switch import RedgtechSwitch
from unittest.mock import AsyncMock, patch, MagicMock
from homeassistant.core import HomeAssistant
from redgtech_api.api import RedgtechConnectionError
from homeassistant.exceptions import HomeAssistantError
from homeassistant.config_entries import ConfigEntryError
from homeassistant.const import STATE_ON, STATE_OFF
@pytest.fixture
def switch_data():
    """Return mock switch data."""
    device = MagicMock()
    device.id = "1234-5678"
    device.name = "Test Switch"
    device.state = STATE_OFF
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
    coordinator.api.set_switch_state = AsyncMock()
    coordinator.access_token = "test_access_token"
    switch = RedgtechSwitch(coordinator, switch_data)
    switch.hass = hass
    switch.entity_id = switch_data.entity_id 
    return switch

@pytest.mark.asyncio
async def test_switch_initial_state(switch):
    """Test the initial state of the switch."""
    assert switch.device_info["name"] == "Test Switch"
    assert switch.is_on is False

@pytest.mark.asyncio
async def test_turn_on_switch(switch):
    """Test turning on the switch."""
    await switch.async_turn_on()
    switch.coordinator.api.set_switch_state.assert_called_once_with("1234-5678", True, "test_access_token")
    assert switch.device.state is STATE_ON

@pytest.mark.asyncio
async def test_turn_off_switch(switch):
    """Test turning off the switch."""
    switch.device.state = True
    await switch.async_turn_off()
    switch.coordinator.api.set_switch_state.assert_called_once_with("1234-5678", False, "test_access_token")
    assert switch.device.state is STATE_OFF

@pytest.mark.asyncio
async def test_handle_connection_error(switch):
    """Test handling of connection errors when turning on the switch."""
    switch.coordinator.api.set_switch_state.side_effect = RedgtechConnectionError
    with pytest.raises(ConfigEntryError):
        await switch.async_turn_on()
