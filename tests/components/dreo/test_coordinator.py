"""Test dreo coordinator."""

from unittest.mock import MagicMock

from hscloud.hscloudexception import HsCloudException
import pytest

from homeassistant.components.dreo.coordinator import (
    DreoDataUpdateCoordinator,
    DreoFanDeviceData,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_coordinator_fan_data_processing_success(hass: HomeAssistant) -> None:
    """Test coordinator successfully processes fan data."""
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


async def test_coordinator_handles_api_errors(hass: HomeAssistant) -> None:
    """Test coordinator handles API errors gracefully."""
    mock_client = MagicMock()
    mock_client.get_status.side_effect = HsCloudException("API Error")

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_client, "test-device-id", "DR-HTF001S"
    )

    with pytest.raises(UpdateFailed, match="Error communicating with Dreo API"):
        await coordinator._async_update_data()

    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert coordinator.data is None


async def test_coordinator_disconnected_device(hass: HomeAssistant) -> None:
    """Test coordinator handles disconnected device."""
    mock_client = MagicMock()
    mock_client.get_status.return_value = {
        "power_switch": False,
        "connected": False,
        "mode": None,
        "speed": 0,
        "oscillate": None,
    }

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_client, "test-device-id", "DR-HTF001S"
    )

    await coordinator.async_refresh()

    assert coordinator.data is not None
    assert coordinator.data.available is False
    assert coordinator.data.is_on is False


async def test_coordinator_partial_device_data(hass: HomeAssistant) -> None:
    """Test coordinator handles partial device data."""
    mock_client = MagicMock()
    mock_client.get_status.return_value = {
        "power_switch": True,
        "connected": True,
    }

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_client, "test-device-id", "DR-HTF001S"
    )

    await coordinator.async_refresh()

    assert coordinator.data is not None
    assert isinstance(coordinator.data, DreoFanDeviceData)
    assert coordinator.data.available is True
    assert coordinator.data.is_on is True
    assert coordinator.data.mode is None
    assert coordinator.data.speed_percentage is None
    assert coordinator.data.oscillate is None


async def test_coordinator_null_status_response(hass: HomeAssistant) -> None:
    """Test coordinator handles null status response."""
    mock_client = MagicMock()
    mock_client.get_status.return_value = None

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_client, "test-device-id", "DR-HTF001S"
    )

    await coordinator.async_refresh()

    assert coordinator.data is None


async def test_coordinator_unsupported_device_model(hass: HomeAssistant) -> None:
    """Test coordinator handles unsupported device model."""
    mock_client = MagicMock()
    mock_client.get_status.return_value = {
        "connected": True,
        "power_switch": True,
    }

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_client, "test-device-id", "UNKNOWN-MODEL"
    )

    await coordinator.async_refresh()

    assert coordinator.data is None


async def test_coordinator_speed_range_conversion(hass: HomeAssistant) -> None:
    """Test coordinator correctly converts speed values."""
    mock_client = MagicMock()

    test_cases = [
        (1, 16),
        (3, 50),
        (6, 100),
    ]

    for speed_value, expected_percentage in test_cases:
        mock_client.get_status.return_value = {
            "connected": True,
            "power_switch": True,
            "speed": speed_value,
        }

        coordinator = DreoDataUpdateCoordinator(
            hass, mock_client, f"test-device-{speed_value}", "DR-HTF001S"
        )

        await coordinator.async_refresh()

        assert isinstance(coordinator.data, DreoFanDeviceData)
        assert coordinator.data.speed_percentage == expected_percentage


async def test_coordinator_unexpected_exception(hass: HomeAssistant) -> None:
    """Test coordinator handles unexpected exceptions."""
    mock_client = MagicMock()
    mock_client.get_status.side_effect = ValueError("Unexpected error")

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_client, "test-device-id", "DR-HTF001S"
    )

    with pytest.raises(UpdateFailed, match="Unexpected error"):
        await coordinator._async_update_data()


async def test_coordinator_device_data_properties(hass: HomeAssistant) -> None:
    """Test DreoFanDeviceData properties and initialization."""
    data = DreoFanDeviceData(
        available=True,
        is_on=True,
        mode="natural",
        oscillate=False,
        speed_percentage=75,
    )

    assert data.available is True
    assert data.is_on is True
    assert data.mode == "natural"
    assert data.oscillate is False
    assert data.speed_percentage == 75

    default_data = DreoFanDeviceData()
    assert default_data.available is False
    assert default_data.is_on is False
    assert default_data.mode is None
    assert default_data.oscillate is None
    assert default_data.speed_percentage is None


async def test_coordinator_data_consistency_across_updates(hass: HomeAssistant) -> None:
    """Test coordinator maintains data consistency across multiple updates."""
    mock_client = MagicMock()

    mock_client.get_status.side_effect = [
        {
            "power_switch": True,
            "connected": True,
            "mode": "auto",
            "speed": 4,
            "oscillate": True,
        },
        {
            "power_switch": False,
            "connected": True,
            "mode": None,
            "speed": 0,
            "oscillate": False,
        },
    ]

    coordinator = DreoDataUpdateCoordinator(
        hass, mock_client, "test-device-id", "DR-HTF001S"
    )

    await coordinator.async_refresh()
    first_data = coordinator.data
    assert first_data is not None
    assert first_data.is_on is True
    assert first_data.mode == "auto"
    assert first_data.speed_percentage == 66

    await coordinator.async_refresh()
    second_data = coordinator.data
    assert second_data is not None
    assert second_data.is_on is False
    assert second_data.mode is None
    assert second_data.speed_percentage == 0
