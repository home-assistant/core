"""Test the Hisense ConnectLife switch platform."""

import pytest
from unittest.mock import AsyncMock, patch

from .common import mock_config_entry, mock_coordinator


@pytest.mark.asyncio
async def test_switch_entity_creation(hass, mock_config_entry, mock_coordinator):
    """Test switch entity creation."""
    from custom_components.hisense_connectlife.switch import HisenseSwitchEntity
    
    device_data = {
        "deviceId": "test_device_123",
        "deviceName": "Test AC",
        "deviceType": "009",
        "featureCode": "199",
        "status": {
            "t_fan_mute": "0"
        }
    }
    
    switch = HisenseSwitchEntity(
        coordinator=mock_coordinator,
        device_data=device_data,
        device_id="test_device_123",
        switch_type="quiet_mode"
    )
    
    assert switch.name == "Test AC Quiet Mode"
    assert not switch.is_on


@pytest.mark.asyncio
async def test_switch_turn_on(hass, mock_config_entry, mock_coordinator):
    """Test turning switch on."""
    from custom_components.hisense_connectlife.switch import HisenseSwitchEntity
    
    device_data = {
        "deviceId": "test_device_123",
        "deviceName": "Test AC",
        "deviceType": "009",
        "featureCode": "199",
        "status": {}
    }
    
    switch = HisenseSwitchEntity(
        coordinator=mock_coordinator,
        device_data=device_data,
        device_id="test_device_123",
        switch_type="quiet_mode"
    )
    
    with patch.object(switch, "async_control_device") as mock_control:
        await switch.async_turn_on()
        mock_control.assert_called_once()
