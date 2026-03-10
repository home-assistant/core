"""Additional edge case tests for LoJack device tracker."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import MockApiError

from tests.common import MockConfigEntry


def _make_client(mock_device: MagicMock) -> AsyncMock:
    """Build a mock client for edge case tests."""
    client = AsyncMock()
    client.user_id = "user123"
    client.list_devices = AsyncMock(return_value=[mock_device])
    client.close = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


async def test_device_tracker_becomes_unavailable_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_location: MagicMock,
) -> None:
    """Test device tracker becomes unavailable when coordinator update fails."""
    mock_device.get_location = AsyncMock(return_value=mock_location)
    client = _make_client(mock_device)

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
        patch(
            "homeassistant.components.lojack.coordinator.ApiError",
            MockApiError,
        ),
    ):
        await setup_integration(hass, mock_config_entry)

        state = hass.states.get("device_tracker.2021_honda_accord")
        assert state is not None
        assert state.state != "unavailable"

        # Simulate location fetch failure on next update
        coordinators = mock_config_entry.runtime_data
        mock_device.get_location = AsyncMock(
            side_effect=MockApiError("API unavailable")
        )

        await coordinators[0].async_refresh()
        await hass.async_block_till_done()

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
) -> None:
    """Test device tracker entity naming with only device name."""
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
    client = _make_client(device)

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
    client = _make_client(mock_device)

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

    state = hass.states.get("device_tracker.2021_honda_accord")
    assert state is not None
    assert state.attributes["gps_accuracy"] == 0
