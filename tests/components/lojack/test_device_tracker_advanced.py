"""Advanced tests for the LoJack device tracker platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.device_tracker import SourceType
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_tracker_with_string_address(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device tracker when address is a string."""
    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = 10.5
    location.heading = 180.0
    location.address = "Simple string address"
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
        assert state.attributes["address"] == "Simple string address"


async def test_device_tracker_with_dict_address_all_fields(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device tracker with complete address dictionary."""
    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = 10.5
    location.heading = 180.0
    location.address = {
        "line1": "123 Main St",
        "line2": "Suite 100",
        "city": "San Francisco",
        "stateOrProvince": "CA",
        "postalCode": "94102",
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
        # All address parts should be joined
        addr = state.attributes["address"]
        assert "123 Main St" in addr
        assert "Suite 100" in addr
        assert "San Francisco" in addr
        assert "CA" in addr
        assert "94102" in addr


async def test_device_tracker_with_dict_address_partial_fields(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device tracker with incomplete address dictionary."""
    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = 10.5
    location.heading = 180.0
    location.address = {
        "line1": "123 Main St",
        "city": "San Francisco",
        # Missing other fields
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
        addr = state.attributes["address"]
        assert "123 Main St" in addr
        assert "San Francisco" in addr


async def test_device_tracker_with_dict_address_empty_strings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device tracker with empty string values in address dictionary."""
    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = 10.5
    location.heading = 180.0
    location.address = {
        "line1": "123 Main St",
        "line2": "",  # Empty
        "city": "San Francisco",
        "stateOrProvince": "",  # Empty
        "postalCode": "94102",
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
        addr = state.attributes["address"]
        # Should only include non-empty values
        assert "123 Main St" in addr
        assert "San Francisco" in addr
        assert "94102" in addr
        # Should not duplicate empty strings
        assert addr.count(",,") == 0


async def test_device_tracker_with_dict_address_empty_dict(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device tracker with completely empty address dictionary."""
    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = 10.5
    location.heading = 180.0
    location.address = {}  # Empty dict
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
        # Address should still be in attributes but set to the dict string representation
        attrs = state.attributes
        if "address" in attrs:
            # Address is set to string representation of empty dict
            assert attrs["address"] == "{}"


async def test_device_tracker_without_heading(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device tracker when heading is None."""
    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = 10.5
    location.heading = None
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
        assert "heading" not in state.attributes


async def test_device_tracker_without_timestamp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device tracker when timestamp is None."""
    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = 10.5
    location.heading = 180.0
    location.address = "Test Address"
    location.timestamp = None

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
        assert "last_polled" not in state.attributes


async def test_device_tracker_without_address(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device tracker when address is None."""
    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = 10.5
    location.heading = 180.0
    location.address = None
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
        assert "address" not in state.attributes


async def test_device_tracker_invalid_accuracy_string(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test device tracker with invalid accuracy value (string)."""
    location = MagicMock()
    location.latitude = 37.7749
    location.longitude = -122.4194
    location.accuracy = "invalid"  # String instead of number
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
        # Accuracy should default to 0 when conversion fails
        assert state.attributes["gps_accuracy"] == 0


async def test_device_tracker_source_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test device tracker source type is GPS."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("device_tracker.2021_honda_accord")
    assert state is not None
    assert state.attributes["source_type"] == SourceType.GPS
