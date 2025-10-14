"""Test the Hisense ConnectLife sensor platform."""

import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.const import UnitOfTemperature, PERCENTAGE

from .common import mock_config_entry, mock_coordinator


@pytest.mark.asyncio
async def test_temperature_sensor(hass, mock_config_entry, mock_coordinator):
    """Test temperature sensor."""
    from custom_components.hisense_connectlife.sensor import HisenseTemperatureSensor
    
    device_data = {
        "deviceId": "test_device_123",
        "deviceName": "Test AC",
        "deviceType": "009",
        "featureCode": "199",
        "status": {
            "f_temp_in": "26.5"
        }
    }
    
    sensor = HisenseTemperatureSensor(
        coordinator=mock_coordinator,
        device_data=device_data,
        device_id="test_device_123",
        sensor_type="indoor_temperature"
    )
    
    assert sensor.name == "Test AC Indoor Temperature"
    assert sensor.unit_of_measurement == UnitOfTemperature.CELSIUS
    assert sensor.native_value == 26.5


@pytest.mark.asyncio
async def test_humidity_sensor(hass, mock_config_entry, mock_coordinator):
    """Test humidity sensor."""
    from custom_components.hisense_connectlife.sensor import HisenseHumiditySensor
    
    device_data = {
        "deviceId": "test_device_123",
        "deviceName": "Test AC",
        "deviceType": "009",
        "featureCode": "199",
        "status": {
            "f_humidity": "65.0"
        }
    }
    
    sensor = HisenseHumiditySensor(
        coordinator=mock_coordinator,
        device_data=device_data,
        device_id="test_device_123"
    )
    
    assert sensor.name == "Test AC Indoor Humidity"
    assert sensor.unit_of_measurement == PERCENTAGE
    assert sensor.native_value == 65.0
