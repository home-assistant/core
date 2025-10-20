"""Test the DayBetter sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_sensor_setup(hass: HomeAssistant) -> None:
    """Test sensor setup."""
    with patch(
        "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
        return_value=[
            {
                "id": "test_device_1",
                "deviceName": "test_sensor",
                "deviceGroupName": "Test Group",
                "type": 5,
                "temperature": 22.5,
                "humidity": 65.0,
            }
        ],
    ):
        entry = await init_integration(hass)
        assert entry.state == "loaded"

        # Check that sensors were created
        temp_sensor = hass.states.get("sensor.test_group_temperature")
        humidity_sensor = hass.states.get("sensor.test_group_humidity")
        
        assert temp_sensor is not None
        assert humidity_sensor is not None
        
        assert temp_sensor.state == "22.5"
        assert humidity_sensor.state == "65.0"


async def test_sensor_attributes(hass: HomeAssistant) -> None:
    """Test sensor attributes."""
    with patch(
        "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
        return_value=[
            {
                "id": "test_device_1",
                "deviceName": "test_sensor",
                "deviceGroupName": "Test Group",
                "type": 5,
                "temperature": 22.5,
                "humidity": 65.0,
            }
        ],
    ):
        entry = await init_integration(hass)
        
        temp_sensor = hass.states.get("sensor.test_group_temperature")
        humidity_sensor = hass.states.get("sensor.test_group_humidity")
        
        # Check temperature sensor attributes
        assert temp_sensor.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
        assert temp_sensor.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
        assert temp_sensor.attributes["state_class"] == SensorStateClass.MEASUREMENT
        
        # Check humidity sensor attributes
        assert humidity_sensor.attributes["unit_of_measurement"] == PERCENTAGE
        assert humidity_sensor.attributes["device_class"] == SensorDeviceClass.HUMIDITY
        assert humidity_sensor.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_sensor_no_devices(hass: HomeAssistant) -> None:
    """Test sensor setup with no devices."""
    with patch(
        "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
        return_value=[],
    ):
        entry = await init_integration(hass)
        assert entry.state == "loaded"
        
        # No sensors should be created
        temp_sensor = hass.states.get("sensor.test_group_temperature")
        humidity_sensor = hass.states.get("sensor.test_group_humidity")
        
        assert temp_sensor is None
        assert humidity_sensor is None


async def test_sensor_wrong_device_type(hass: HomeAssistant) -> None:
    """Test sensor setup with wrong device type."""
    with patch(
        "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
        return_value=[
            {
                "id": "test_device_1",
                "deviceName": "test_device",
                "deviceGroupName": "Test Group",
                "type": 1,  # Not a sensor device
                "temperature": 22.5,
                "humidity": 65.0,
            }
        ],
    ):
        entry = await init_integration(hass)
        assert entry.state == "loaded"
        
        # No sensors should be created for wrong device type
        temp_sensor = hass.states.get("sensor.test_group_temperature")
        humidity_sensor = hass.states.get("sensor.test_group_humidity")
        
        assert temp_sensor is None
        assert humidity_sensor is None
