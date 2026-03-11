"""Tests for LoJack coordinator with multiple devices."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


def _make_device(
    device_id: str,
    name: str,
    vin: str,
    make: str,
    model: str,
    year: int,
    location: MagicMock | None,
) -> MagicMock:
    """Create a mock device."""
    device = MagicMock()
    device.id = device_id
    device.name = name
    device.vin = vin
    device.make = make
    device.model = model
    device.year = year
    device.get_location = AsyncMock(return_value=location)
    return device


async def test_coordinator_multiple_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test separate coordinators are created for multiple devices."""
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

    device1 = _make_device("device1", "Car 1", "VIN1", "Honda", "Accord", 2021, location1)
    device2 = _make_device("device2", "Car 2", "VIN2", "Toyota", "Camry", 2022, location2)

    client = AsyncMock()
    client.user_id = "user123"
    client.list_devices = AsyncMock(return_value=[device1, device2])
    client.close = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch("homeassistant.components.lojack.PLATFORMS", [Platform.DEVICE_TRACKER]),
    ):
        await setup_integration(hass, mock_config_entry)

    coordinators = mock_config_entry.runtime_data
    assert len(coordinators) == 2

    # Verify both coordinators have correct data
    ids = {c.data.device_id for c in coordinators}
    assert ids == {"device1", "device2"}

    by_id = {c.data.device_id: c.data for c in coordinators}
    assert by_id["device1"].latitude == 37.7749
    assert by_id["device1"].longitude == -122.4194
    assert by_id["device2"].latitude == 40.7128
    assert by_id["device2"].longitude == -74.0060


async def test_coordinator_multiple_devices_one_no_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinators when one device returns None for location."""
    location1 = MagicMock()
    location1.latitude = 37.7749
    location1.longitude = -122.4194
    location1.accuracy = 10.5
    location1.heading = 180.0
    location1.address = "Address 1"
    location1.timestamp = "2020-02-02T14:00:00Z"

    device1 = _make_device("device1", "Car 1", "VIN1", "Honda", "Accord", 2021, location1)
    device2 = _make_device("device2", "Car 2", "VIN2", "Toyota", "Camry", 2022, None)

    client = AsyncMock()
    client.user_id = "user123"
    client.list_devices = AsyncMock(return_value=[device1, device2])
    client.close = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch("homeassistant.components.lojack.PLATFORMS", [Platform.DEVICE_TRACKER]),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinators = mock_config_entry.runtime_data
    assert len(coordinators) == 2

    by_id = {c.data.device_id: c.data for c in coordinators}
    # device1 has location
    assert by_id["device1"].latitude == 37.7749
    # device2 has no location (returned None)
    assert by_id["device2"].latitude is None


async def test_coordinator_empty_device_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles empty device list."""
    client = AsyncMock()
    client.user_id = "user123"
    client.list_devices = AsyncMock(return_value=[])
    client.close = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch("homeassistant.components.lojack.PLATFORMS", [Platform.DEVICE_TRACKER]),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data == []
    client.close.assert_called_once()
