"""Tests for the Dreo coordinator."""

from unittest.mock import MagicMock, patch

from hscloud.hscloudexception import HsCloudException
import pytest

from homeassistant.components.dreo.coordinator import (
    DeviceDataFactory,
    DreoDataUpdateCoordinator,
    DreoFanDeviceData,
    DreoGenericDeviceData,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_coordinator_update_success(hass: HomeAssistant) -> None:
    """Test successful coordinator update."""
    mock_client = MagicMock()
    mock_client.get_status.return_value = {
        "power_switch": True,
        "connected": True,
        "mode": "auto",
        "speed": 3,
        "oscillate": True,
    }

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_client, "test-device-id", "DR-HTF001S"
    )

    await coordinator.async_refresh()

    assert coordinator.data is not None
    assert isinstance(coordinator.data, DreoFanDeviceData)
    assert coordinator.data.available is True
    assert coordinator.data.is_on is True
    assert coordinator.data.mode == "auto"
    assert coordinator.data.oscillate is True
    assert coordinator.data.speed_percentage == 50


async def test_coordinator_update_error(hass: HomeAssistant) -> None:
    """Test coordinator update with API error."""
    mock_client = MagicMock()
    mock_client.get_status.side_effect = HsCloudException("Test error")

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_client, "test-device-id", "DR-HTF001S"
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    await coordinator.async_refresh()
    assert coordinator.last_update_success is False

    assert coordinator.data is None


async def test_coordinator_disconnected_device(
    hass: HomeAssistant, mock_dreo_client
) -> None:
    """Test coordinator with disconnected device."""
    mock_dreo_client.get_status.return_value = {
        "power_switch": False,
        "connected": False,
        "mode": None,
        "speed": 0,
        "oscillate": None,
    }

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_dreo_client, "test-device-id", "DR-HTF001S"
    )

    await coordinator.async_refresh()

    assert coordinator.data is not None
    assert coordinator.data.available is False


async def test_coordinator_missing_data(hass: HomeAssistant, mock_dreo_client) -> None:
    """Test coordinator with missing data."""
    mock_dreo_client.get_status.return_value = {
        "power_switch": True,
        "connected": True,
    }

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_dreo_client, "test-device-id", "DR-HTF001S"
    )

    await coordinator.async_refresh()

    assert coordinator.data is not None
    assert isinstance(coordinator.data, DreoFanDeviceData)
    assert coordinator.data.available is True
    assert coordinator.data.is_on is True
    assert coordinator.data.mode is None
    assert coordinator.data.speed_percentage is None
    assert coordinator.data.oscillate is None


async def test_fan_device_data_init() -> None:
    """Test DreoFanDeviceData initialization."""
    data = DreoFanDeviceData(
        available=True,
        is_on=True,
        mode="auto",
        oscillate=True,
        speed_percentage=75,
    )

    assert data.available is True
    assert data.is_on is True
    assert data.mode == "auto"
    assert data.oscillate is True
    assert data.speed_percentage == 75


async def test_coordinator_unsupported_device(hass: HomeAssistant) -> None:
    """Test coordinator with unsupported device type."""
    mock_client = MagicMock()
    mock_client.get_status.return_value = {
        "connected": True,
        "power_switch": True,
    }

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_client, "test-device-id", "UNKNOWN-MODEL"
    )

    await coordinator.async_refresh()

    assert isinstance(coordinator.data, DreoGenericDeviceData)
    assert coordinator.data.available is False
    assert coordinator.data.is_on is False


async def test_coordinator_speed_conversion(hass: HomeAssistant) -> None:
    """Test speed conversion in coordinator."""
    model = "DR-HTF001S"
    speed_range = (1, 6)
    raw_speed = 1
    expected_percentage = 16

    with patch(
        "homeassistant.components.dreo.coordinator.FAN_DEVICE",
        {
            "type": "fan",
            "config": {model: {"speed_range": speed_range}},
        },
    ):
        mock_client = MagicMock()
        mock_client.get_status.return_value = {
            "connected": True,
            "power_switch": True,
            "speed": raw_speed,
        }

        coordinator = DreoDataUpdateCoordinator(
            hass, mock_client, "test-device-id", model
        )

        await coordinator.async_refresh()

        assert isinstance(coordinator.data, DreoFanDeviceData)
        assert coordinator.data.speed_percentage == expected_percentage


async def test_device_data_factory_create_data(
    hass: HomeAssistant, mock_dreo_client
) -> None:
    """Test DeviceDataFactory.create_data method."""
    fan_coordinator = DreoDataUpdateCoordinator(
        hass, mock_dreo_client, "test-device-id", "DR-HTF001S"
    )
    fan_coordinator.device_type = "fan"

    fan_status = {
        "power_switch": True,
        "connected": True,
        "mode": "auto",
        "speed": 3,
        "oscillate": True,
    }

    fan_data = DeviceDataFactory.create_data(fan_coordinator, fan_status)
    assert isinstance(fan_data, DreoFanDeviceData)
    assert fan_data.available is True
    assert fan_data.is_on is True
    assert fan_data.mode == "auto"
    assert fan_data.oscillate is True

    unknown_coordinator = DreoDataUpdateCoordinator(
        hass, mock_dreo_client, "test-device-id", "UNKNOWN-MODEL"
    )
    unknown_coordinator.device_type = "unknown"

    unknown_data = DeviceDataFactory.create_data(unknown_coordinator, fan_status)
    assert unknown_data is None


async def test_coordinator_none_status(hass: HomeAssistant, mock_dreo_client) -> None:
    """Test coordinator handling when get_status returns None."""
    mock_dreo_client.get_status.return_value = None

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_dreo_client, "test-device-id", "DR-HTF001S"
    )

    await coordinator.async_refresh()

    assert coordinator.data is None


async def test_coordinator_unexpected_exception(
    hass: HomeAssistant, mock_dreo_client
) -> None:
    """Test coordinator handling of unexpected exceptions."""
    mock_dreo_client.get_status.side_effect = Exception("Unexpected error")

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_dreo_client, "test-device-id", "DR-HTF001S"
    )

    with pytest.raises(UpdateFailed, match="Unexpected error"):
        await coordinator._async_update_data()
