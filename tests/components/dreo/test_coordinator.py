"""Test dreo coordinator core logic.

Only tests for core logic that cannot be tested through platforms should be here.
Most coordinator functionality should be tested through platform tests (test_fan.py).
"""

from unittest.mock import AsyncMock, Mock

from hscloud.hscloudexception import HsCloudException
import pytest

from homeassistant.components.dreo.coordinator import (
    DreoDataUpdateCoordinator,
    DreoFanDeviceData,
    DreoGenericDeviceData,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_speed_range_conversion_logic() -> None:
    """Test speed range conversion algorithm - core logic that spans multiple platforms."""

    test_cases = [
        ({"speed": 1}, 16),
        ({"speed": 3}, 50),
        ({"speed": 6}, 100),
        ({"speed": 0}, 0),
    ]

    for status, expected_percentage in test_cases:
        status.update({"connected": True, "power_switch": True})
        model_config = {
            "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
            "speed_range": [1, 6],
        }
        fan_data = DreoFanDeviceData.process_fan_data(status, model_config)
        assert fan_data.speed_percentage == expected_percentage


async def test_data_processing_with_missing_model_config() -> None:
    """Test data processing behavior when device model is not in configuration."""
    status = {"connected": True, "power_switch": True, "speed": 3}
    model_config = {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
    }
    fan_data = DreoFanDeviceData.process_fan_data(status, model_config)

    assert fan_data.available is True
    assert fan_data.is_on is True

    assert fan_data.speed_percentage is None


async def test_data_type_conversion_algorithms() -> None:
    """Test core data type conversion algorithms used across platforms."""
    status = {
        "connected": True,
        "power_switch": True,
        "mode": 123,
        "oscillate": 1,
        "speed": 3,
    }
    model_config = {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": [1, 6],
    }

    fan_data = DreoFanDeviceData.process_fan_data(status, model_config)

    assert fan_data.mode == "123"
    assert fan_data.oscillate is True
    assert fan_data.speed_percentage == 50


async def test_generic_device_data_initialization() -> None:
    """Test DreoGenericDeviceData initialization with different parameters."""

    generic_data = DreoGenericDeviceData()
    assert generic_data.available is False
    assert generic_data.is_on is False

    generic_data_custom = DreoGenericDeviceData(available=True, is_on=True)
    assert generic_data_custom.available is True
    assert generic_data_custom.is_on is True


async def test_fan_device_data_initialization() -> None:
    """Test DreoFanDeviceData initialization with different parameters."""

    fan_data = DreoFanDeviceData()
    assert fan_data.available is False
    assert fan_data.is_on is False
    assert fan_data.mode is None
    assert fan_data.oscillate is None
    assert fan_data.speed_percentage is None

    fan_data_custom = DreoFanDeviceData(
        available=True, is_on=True, mode="Normal", oscillate=True, speed_percentage=75
    )
    assert fan_data_custom.available is True
    assert fan_data_custom.is_on is True
    assert fan_data_custom.mode == "Normal"
    assert fan_data_custom.oscillate is True
    assert fan_data_custom.speed_percentage == 75


async def test_coordinator_unsupported_device_type() -> None:
    """Test coordinator behavior with unsupported device types."""
    hass = Mock(spec=HomeAssistant)
    client = Mock()
    device_id = "test_device"
    device_type = "unsupported_type"
    model_config = {"preset_modes": ["Sleep", "Auto", "Natural", "Normal"]}

    coordinator = DreoDataUpdateCoordinator(
        hass, client, device_id, device_type, model_config
    )

    assert coordinator.data_processor is None


async def test_coordinator_async_update_data_no_status() -> None:
    """Test coordinator update when no status is available."""
    hass = Mock(spec=HomeAssistant)
    client = Mock()
    device_id = "test_device"
    device_type = "fan"
    model_config = {"preset_modes": ["Sleep", "Auto", "Natural", "Normal"]}

    hass.async_add_executor_job = AsyncMock(return_value=None)

    coordinator = DreoDataUpdateCoordinator(
        hass, client, device_id, device_type, model_config
    )

    with pytest.raises(UpdateFailed, match="No status available"):
        await coordinator._async_update_data()


async def test_coordinator_async_update_data_no_processor() -> None:
    """Test coordinator update when no data processor is available."""
    hass = Mock(spec=HomeAssistant)
    client = Mock()
    device_id = "test_device"
    device_type = "unsupported_type"
    model_config = {"preset_modes": ["Sleep", "Auto", "Natural", "Normal"]}

    hass.async_add_executor_job = AsyncMock(return_value={"connected": True})

    coordinator = DreoDataUpdateCoordinator(
        hass, client, device_id, device_type, model_config
    )

    with pytest.raises(UpdateFailed, match="No data processor available"):
        await coordinator._async_update_data()


async def test_coordinator_async_update_data_hscloud_exception() -> None:
    """Test coordinator update when HsCloudException is raised."""
    hass = Mock(spec=HomeAssistant)
    client = Mock()
    device_id = "test_device"
    device_type = "fan"
    model_config = {"preset_modes": ["Sleep", "Auto", "Natural", "Normal"]}

    hass.async_add_executor_job = AsyncMock(side_effect=HsCloudException("API Error"))

    coordinator = DreoDataUpdateCoordinator(
        hass, client, device_id, device_type, model_config
    )

    with pytest.raises(UpdateFailed, match="Error communicating with Dreo API"):
        await coordinator._async_update_data()


async def test_coordinator_async_update_data_unexpected_exception() -> None:
    """Test coordinator update when unexpected exception is raised."""
    hass = Mock(spec=HomeAssistant)
    client = Mock()
    device_id = "test_device"
    device_type = "fan"
    model_config = {"preset_modes": ["Sleep", "Auto", "Natural", "Normal"]}

    hass.async_add_executor_job = AsyncMock(side_effect=ValueError("Unexpected error"))

    coordinator = DreoDataUpdateCoordinator(
        hass, client, device_id, device_type, model_config
    )

    with pytest.raises(UpdateFailed, match="Unexpected error"):
        await coordinator._async_update_data()


async def test_process_fan_data_edge_cases() -> None:
    """Test edge cases in fan data processing."""

    status = {"connected": False, "power_switch": False}
    model_config = {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": [1, 6],
    }

    fan_data = DreoFanDeviceData.process_fan_data(status, model_config)
    assert fan_data.available is False
    assert fan_data.is_on is False
    assert fan_data.mode is None
    assert fan_data.oscillate is None
    assert fan_data.speed_percentage is None


    status_zero_oscillate = {
        "connected": True,
        "power_switch": True,
        "oscillate": 0,
        "speed": 3,
    }

    fan_data_zero = DreoFanDeviceData.process_fan_data(
        status_zero_oscillate, model_config
    )
    assert fan_data_zero.oscillate is False
    assert fan_data_zero.speed_percentage == 50
