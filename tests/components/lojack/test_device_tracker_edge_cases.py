"""Additional edge case tests for LoJack device tracker."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_tracker_vehicle_no_longer_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_location: MagicMock,
) -> None:
    """Test device tracker when vehicle is no longer in coordinator data."""
    mock_device.get_location = AsyncMock(return_value=mock_location)

    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[mock_device])
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

        # Verify entity is initially available
        state = hass.states.get("device_tracker.2021_honda_accord")
        assert state is not None
        assert state.state != "unavailable"

        # Simulate vehicle removed from account - client returns empty list
        client.list_devices = AsyncMock(return_value=[])

        # Trigger coordinator update
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Entity should now be unavailable
        state = hass.states.get("device_tracker.2021_honda_accord")
        assert state is not None
        assert state.state == "unavailable"


async def test_device_tracker_battery_level(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test device tracker battery level property."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("device_tracker.2021_honda_accord")
    assert state is not None
    # Battery level should always be None for LoJack devices
    assert state.attributes.get("battery_level") is None


async def test_device_tracker_with_only_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device tracker entity naming with only device name."""
    # Device with only name, no year/make/model
    device = MagicMock()
    device.id = "device456"
    device.name = "My Vehicle"
    device.vin = None
    device.make = None
    device.model = None
    device.year = None

    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = 10.5
    location.heading = 180.0
    location.address = "Test Address"
    location.timestamp = "2020-02-02T14:00:00Z"

    device.get_location = AsyncMock(return_value=location)

    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[device])
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

        state = hass.states.get("device_tracker.my_vehicle")
        assert state is not None


async def test_device_tracker_location_accuracy_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device tracker when accuracy is None."""
    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = None
    location.heading = 180.0
    location.address = "Test Address"
    location.timestamp = "2020-02-02T14:00:00Z"

    mock_device.get_location = AsyncMock(return_value=location)

    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[mock_device])
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

        state = hass.states.get("device_tracker.2021_honda_accord")
        assert state is not None
        assert state.attributes["gps_accuracy"] == 0


async def test_device_tracker_with_model_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device info when only model is available."""
    # Device with year/model but no make
    device = MagicMock()
    device.id = "device789"
    device.name = "Car"
    device.vin = "VIN123"
    device.make = None
    device.model = "Civic"
    device.year = "2020"

    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = 10.5
    location.heading = 180.0
    location.address = "Test Address"
    location.timestamp = "2020-02-02T14:00:00Z"

    device.get_location = AsyncMock(return_value=location)

    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[device])
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


async def test_device_tracker_address_with_numeric_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device tracker address formatting with numeric values."""
    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = 10.5
    location.heading = 180.0
    location.address = {
        "line1": 123,  # Numeric instead of string
        "city": "City",
        "postalCode": 94102,  # Numeric
    }
    location.timestamp = "2020-02-02T14:00:00Z"

    mock_device.get_location = AsyncMock(return_value=location)

    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[mock_device])
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

        state = hass.states.get("device_tracker.2021_honda_accord")
        assert state is not None
        # Should successfully format address with numeric values converted to strings
        attrs = state.attributes
        assert "address" in attrs
        assert attrs["address"] == "123, City, 94102"
