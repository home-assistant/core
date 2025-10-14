"""Test the Hisense ConnectLife number platform."""

import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.components.number import NumberDeviceClass

from .common import mock_config_entry, mock_coordinator


@pytest.mark.asyncio
async def test_number_entity_creation(hass, mock_config_entry, mock_coordinator):
    """Test number entity creation."""
    from custom_components.hisense_connectlife.number import HisenseNumberEntity
    
    device_data = {
        "deviceId": "test_device_123",
        "deviceName": "Test AC",
        "deviceType": "009",
        "featureCode": "199",
        "status": {
            "t_temp": "25"
        }
    }
    
    entity = HisenseNumberEntity(
        coordinator=mock_coordinator,
        device_data=device_data,
        device_id="test_device_123",
        number_type="target_temperature"
    )
    
    assert entity.name == "Test AC Target Temperature"
    assert entity.device_class == NumberDeviceClass.TEMPERATURE
    assert entity.native_value == 25


@pytest.mark.asyncio
async def test_number_set_value(hass, mock_config_entry, mock_coordinator):
    """Test setting number value."""
    from custom_components.hisense_connectlife.number import HisenseNumberEntity
    
    device_data = {
        "deviceId": "test_device_123",
        "deviceName": "Test AC",
        "deviceType": "009",
        "featureCode": "199",
        "status": {}
    }
    
    entity = HisenseNumberEntity(
        coordinator=mock_coordinator,
        device_data=device_data,
        device_id="test_device_123",
        number_type="target_temperature"
    )
    
    with patch.object(entity, "async_control_device") as mock_control:
        await entity.async_set_native_value(value=24)
        mock_control.assert_called_once()
