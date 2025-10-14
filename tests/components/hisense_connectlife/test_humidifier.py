"""Test the Hisense ConnectLife humidifier platform."""

import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.components.humidifier import HumidifierAction, HumidifierEntityFeature

from .common import mock_config_entry, mock_coordinator


@pytest.mark.asyncio
async def test_humidifier_entity_creation(hass, mock_config_entry, mock_coordinator):
    """Test humidifier entity creation."""
    from custom_components.hisense_connectlife.humidifier import HisenseHumidifierEntity
    
    device_data = {
        "deviceId": "test_device_123",
        "deviceName": "Test Humidifier",
        "deviceType": "007",
        "featureCode": "xxx",
        "status": {
            "t_power": "1",
            "t_humidity": "50"
        }
    }
    
    entity = HisenseHumidifierEntity(
        coordinator=mock_coordinator,
        device_data=device_data,
        device_id="test_device_123"
    )
    
    assert entity.name == "Test Humidifier"
    assert entity.supported_features == HumidifierEntityFeature.MODES
    assert entity.is_on


@pytest.mark.asyncio
async def test_humidifier_set_humidity(hass, mock_config_entry, mock_coordinator):
    """Test setting target humidity."""
    from custom_components.hisense_connectlife.humidifier import HisenseHumidifierEntity
    
    device_data = {
        "deviceId": "test_device_123",
        "deviceName": "Test Humidifier",
        "deviceType": "007",
        "featureCode": "xxx",
        "status": {}
    }
    
    entity = HisenseHumidifierEntity(
        coordinator=mock_coordinator,
        device_data=device_data,
        device_id="test_device_123"
    )
    
    with patch.object(entity, "async_control_device") as mock_control:
        await entity.async_set_humidity(target_humidity=60)
        mock_control.assert_called_once()
