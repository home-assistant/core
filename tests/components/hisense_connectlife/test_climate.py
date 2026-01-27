"""Test the Hisense ConnectLife climate platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.hisense_connectlife.climate import HisenseClimate
from homeassistant.components.hisense_connectlife.models import DeviceInfo
from homeassistant.const import UnitOfTemperature


@pytest.mark.asyncio
async def test_climate_entity_creation(mock_coordinator) -> None:
    """Test climate entity creation."""

    # Mock device data
    device_data = {
        "deviceId": "test_device_123",
        "puid": "test_puid_123",
        "deviceNickName": "Test AC",
        "deviceTypeCode": "009",
        "deviceFeatureCode": "199",
        "deviceTypeName": "Air Conditioner",
        "deviceFeatureName": "Split AC",
        "statusList": {
            "t_power": "1",
            "t_work_mode": "cool",
            "t_temp": "25",
            "f_temp_in": "26",
        },
    }

    # Create DeviceInfo object
    device = DeviceInfo(device_data)

    # Mock coordinator's api_client
    mock_coordinator.api_client = MagicMock()
    mock_coordinator.api_client.parsers = MagicMock()
    mock_coordinator.api_client.parsers.get = MagicMock(return_value=None)
    mock_coordinator.api_client.static_data = MagicMock()
    mock_coordinator.api_client.static_data.get = MagicMock(return_value=None)

    entity = HisenseClimate(
        coordinator=mock_coordinator,
        device=device,
    )

    assert entity._attr_name == "Test AC"
    assert entity._attr_temperature_unit == UnitOfTemperature.CELSIUS


@pytest.mark.asyncio
async def test_climate_set_temperature(mock_coordinator) -> None:
    """Test setting temperature."""

    device_data = {
        "deviceId": "test_device_123",
        "puid": "test_puid_123",
        "deviceNickName": "Test AC",
        "deviceTypeCode": "009",
        "deviceFeatureCode": "199",
        "deviceTypeName": "Air Conditioner",
        "deviceFeatureName": "Split AC",
        "statusList": {
            "t_power": "1",
            "t_work_mode": "cool",
        },
    }

    # Create DeviceInfo object
    device = DeviceInfo(device_data)

    # Mock coordinator's api_client
    mock_coordinator.api_client = MagicMock()
    mock_coordinator.api_client.parsers = MagicMock()
    mock_coordinator.api_client.parsers.get = MagicMock(return_value=None)
    mock_coordinator.api_client.static_data = MagicMock()
    mock_coordinator.api_client.static_data.get = MagicMock(return_value=None)

    # Mock coordinator.async_control_device
    mock_coordinator.async_control_device = AsyncMock()

    entity = HisenseClimate(
        coordinator=mock_coordinator,
        device=device,
    )

    await entity.async_set_temperature(temperature=24)
    mock_coordinator.async_control_device.assert_called_once()
