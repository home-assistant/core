"""Test the Hisense ConnectLife water heater platform."""

import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.components.water_heater import STATE_ELECTRIC, STATE_OFF
from homeassistant.const import UnitOfTemperature

from .common import mock_config_entry, mock_coordinator


@pytest.mark.asyncio
async def test_water_heater_entity_creation(hass, mock_config_entry, mock_coordinator):
    """Test water heater entity creation."""
    from custom_components.hisense_connectlife.water_heater import HisenseWaterHeaterEntity
    
    device_data = {
        "deviceId": "test_device_123",
        "deviceName": "Test Water Heater",
        "deviceType": "035",
        "featureCode": "699",
        "status": {
            "t_power": "1",
            "t_work_mode": "electric",
            "t_water_temp": "45"
        }
    }
    
    entity = HisenseWaterHeaterEntity(
        coordinator=mock_coordinator,
        device_data=device_data,
        device_id="test_device_123"
    )
    
    assert entity.name == "Test Water Heater"
    assert entity.temperature_unit == UnitOfTemperature.CELSIUS
    assert entity.current_operation == STATE_ELECTRIC


@pytest.mark.asyncio
async def test_water_heater_set_temperature(hass, mock_config_entry, mock_coordinator):
    """Test setting water heater temperature."""
    from custom_components.hisense_connectlife.water_heater import HisenseWaterHeaterEntity
    
    device_data = {
        "deviceId": "test_device_123",
        "deviceName": "Test Water Heater",
        "deviceType": "035",
        "featureCode": "699",
        "status": {}
    }
    
    entity = HisenseWaterHeaterEntity(
        coordinator=mock_coordinator,
        device_data=device_data,
        device_id="test_device_123"
    )
    
    with patch.object(entity, "async_control_device") as mock_control:
        await entity.async_set_temperature(temperature=50)
        mock_control.assert_called_once()
