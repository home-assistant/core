"""Tests for LoJack coordinator with multiple devices."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_coordinator_multiple_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator fetches data for multiple devices."""
    # Create multiple mock devices
    device1 = MagicMock()
    device1.id = "device1"
    device1.name = "Car 1"
    device1.vin = "VIN1"
    device1.make = "Honda"
    device1.model = "Accord"
    device1.year = "2021"

    device2 = MagicMock()
    device2.id = "device2"
    device2.name = "Car 2"
    device2.vin = "VIN2"
    device2.make = "Toyota"
    device2.model = "Camry"
    device2.year = "2022"

    location1 = MagicMock()
    location1.latitude = 37.7749
    location1.longitude = -122.4194
    location1.accuracy = 10.5
    location1.heading = 180.0
    location1.address = "Address 1"
    location1.timestamp = "2020-02-02T14:00:00Z"

    location2 = MagicMock()
    location2.latitude = 40.7128
    location2.longitude = -74.0060
    location2.accuracy = 15.0
    location2.heading = 90.0
    location2.address = "Address 2"
    location2.timestamp = "2020-02-02T14:01:00Z"

    device1.get_location = AsyncMock(return_value=location1)
    device2.get_location = AsyncMock(return_value=location2)

    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[device1, device2])
    client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=client,
        ),
    ):
        with patch("homeassistant.components.lojack.PLATFORMS", [Platform.DEVICE_TRACKER]):
            await setup_integration(hass, mock_config_entry)

        coordinator = mock_config_entry.runtime_data
        assert coordinator.data is not None
        assert len(coordinator.data) == 2
        assert "device1" in coordinator.data
        assert "device2" in coordinator.data

        # Verify both devices have correct data
        device1_data = coordinator.data["device1"]
        assert device1_data.latitude == 37.7749
        assert device1_data.longitude == -122.4194

        device2_data = coordinator.data["device2"]
        assert device2_data.latitude == 40.7128
        assert device2_data.longitude == -74.0060


async def test_coordinator_multiple_devices_mixed_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles mixed success/failure for multiple devices."""
    device1 = MagicMock()
    device1.id = "device1"
    device1.name = "Car 1"
    device1.vin = "VIN1"
    device1.make = "Honda"
    device1.model = "Accord"
    device1.year = "2021"

    device2 = MagicMock()
    device2.id = "device2"
    device2.name = "Car 2"
    device2.vin = "VIN2"
    device2.make = "Toyota"
    device2.model = "Camry"
    device2.year = "2022"

    location1 = MagicMock()
    location1.latitude = 37.7749
    location1.longitude = -122.4194
    location1.accuracy = 10.5
    location1.heading = 180.0
    location1.address = "Address 1"
    location1.timestamp = "2020-02-02T14:00:00Z"

    device1.get_location = AsyncMock(return_value=location1)
    device2.get_location = AsyncMock(side_effect=Exception("Location unavailable"))

    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[device1, device2])
    client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=client,
        ),
    ):
        with patch("homeassistant.components.lojack.PLATFORMS", [Platform.DEVICE_TRACKER]):
            await setup_integration(hass, mock_config_entry)

        coordinator = mock_config_entry.runtime_data
        assert coordinator.data is not None
        # Both devices should be in data, even if one failed location fetch
        assert len(coordinator.data) == 2

        # device1 should have location
        device1_data = coordinator.data["device1"]
        assert device1_data.latitude == 37.7749

        # device2 should not have location
        device2_data = coordinator.data["device2"]
        assert device2_data.latitude is None


async def test_coordinator_empty_device_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles empty device list."""
    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[])
    client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=client,
        ),
    ):
        with patch("homeassistant.components.lojack.PLATFORMS", [Platform.DEVICE_TRACKER]):
            await setup_integration(hass, mock_config_entry)

        coordinator = mock_config_entry.runtime_data
        assert coordinator.data is not None
        assert len(coordinator.data) == 0
