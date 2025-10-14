"""Test the Hisense ConnectLife climate platform."""

import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.components.climate import HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .common import mock_config_entry, mock_coordinator


@pytest.mark.asyncio
async def test_climate_entity_creation(hass, mock_config_entry, mock_coordinator):
    """Test climate entity creation."""
    from custom_components.hisense_connectlife.climate import HisenseClimateEntity
    
    # Mock device data
    device_data = {
        "deviceId": "test_device_123",
        "deviceName": "Test AC",
        "deviceType": "009",
        "featureCode": "199",
        "status": {
            "t_power": "1",
            "t_work_mode": "cool",
            "t_temp": "25",
            "f_temp_in": "26",
        }
    }
    
    entity = HisenseClimateEntity(
        coordinator=mock_coordinator,
        device_data=device_data,
        device_id="test_device_123"
    )
    
    assert entity.name == "Test AC"
    assert entity.temperature_unit == UnitOfTemperature.CELSIUS
    assert entity.hvac_mode == HVACMode.COOL


@pytest.mark.asyncio
async def test_climate_set_temperature(hass, mock_config_entry, mock_coordinator):
    """Test setting temperature."""
    from custom_components.hisense_connectlife.climate import HisenseClimateEntity
    
    device_data = {
        "deviceId": "test_device_123",
        "deviceName": "Test AC",
        "deviceType": "009",
        "featureCode": "199",
        "status": {}
    }
    
    entity = HisenseClimateEntity(
        coordinator=mock_coordinator,
        device_data=device_data,
        device_id="test_device_123"
    )
    
    with patch.object(entity, "async_control_device") as mock_control:
        await entity.async_set_temperature(temperature=24)
        mock_control.assert_called_once()
