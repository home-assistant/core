"""Test the Vitrea coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from vitreaclient.constants import DeviceStatus

from homeassistant.components.vitrea.coordinator import VitreaCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_handle_unhandled_device_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test coordinator handles unhandled device status."""
    coordinator = VitreaCoordinator(hass, mock_vitrea_client, mock_config_entry)

    # Create event with unknown status
    mock_event = MagicMock()
    mock_event.node = "01"
    mock_event.key = "01"
    mock_event.status = "UNKNOWN_STATUS"  # Not in DEVICE_STATUS_TO_PLATFORM map
    mock_event.data = "050"

    # This should log debug and return early
    with patch("homeassistant.components.vitrea.coordinator._LOGGER") as mock_logger:
        coordinator._handle_status_event(mock_event)
        mock_logger.debug.assert_called_once_with(
            "Unhandled device status: %s", "UNKNOWN_STATUS"
        )

    # Data should not be updated
    assert coordinator.data is None or "01_01" not in (coordinator.data or {})


async def test_coordinator_no_callback_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test coordinator warning when no callback registered for platform."""
    coordinator = VitreaCoordinator(hass, mock_vitrea_client, mock_config_entry)

    # Don't register any callbacks
    # coordinator.set_entity_add_callback("cover", ...)

    # Create event
    mock_event = MagicMock()
    mock_event.node = "01"
    mock_event.key = "01"
    mock_event.status = DeviceStatus.BLIND
    mock_event.data = "050"

    with patch("homeassistant.components.vitrea.coordinator._LOGGER") as mock_logger:
        coordinator._handle_status_event(mock_event)

        # Should warn about no callback
        mock_logger.warning.assert_called_once_with(
            "No callback registered for platform %s", "cover"
        )


async def test_coordinator_update_data_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test coordinator handles connection error during update."""
    coordinator = VitreaCoordinator(hass, mock_vitrea_client, mock_config_entry)

    # Make status_request raise ConnectionError
    mock_vitrea_client.status_request.side_effect = ConnectionError("Connection lost")

    with pytest.raises(UpdateFailed, match="Error communicating with Vitrea"):
        await coordinator._async_update_data()


async def test_coordinator_update_data_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test coordinator handles timeout error during update."""
    coordinator = VitreaCoordinator(hass, mock_vitrea_client, mock_config_entry)

    # Make status_request raise TimeoutError
    mock_vitrea_client.status_request.side_effect = TimeoutError("Request timeout")

    with pytest.raises(UpdateFailed, match="Error communicating with Vitrea"):
        await coordinator._async_update_data()


async def test_coordinator_update_data_generic_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test coordinator handles generic error during update."""
    coordinator = VitreaCoordinator(hass, mock_vitrea_client, mock_config_entry)

    # Make status_request raise generic Exception
    mock_vitrea_client.status_request.side_effect = RuntimeError("Unexpected error")

    with pytest.raises(UpdateFailed, match="Vitrea API error"):
        await coordinator._async_update_data()


async def test_coordinator_async_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test coordinator handles setup error."""
    coordinator = VitreaCoordinator(hass, mock_vitrea_client, mock_config_entry)

    # Make connect raise an error
    mock_vitrea_client.connect.side_effect = RuntimeError("Setup failed")

    with pytest.raises(RuntimeError, match="Setup failed"):
        await coordinator.async_setup()


async def test_coordinator_async_shutdown_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test coordinator handles error during shutdown."""
    coordinator = VitreaCoordinator(hass, mock_vitrea_client, mock_config_entry)

    # Make disconnect raise an error
    mock_vitrea_client.disconnect.side_effect = ConnectionError("Disconnect failed")

    # Should log warning but not raise
    with patch("homeassistant.components.vitrea.coordinator._LOGGER") as mock_logger:
        await coordinator.async_shutdown()
        mock_logger.warning.assert_called_once()


async def test_coordinator_get_entities_by_platform_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test get_entities_by_platform when no data."""
    coordinator = VitreaCoordinator(hass, mock_vitrea_client, mock_config_entry)

    # No data yet
    assert coordinator.data is None

    result = coordinator.get_entities_by_platform("cover")
    assert result == {}


async def test_coordinator_get_entities_by_platform_with_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test get_entities_by_platform with data."""
    coordinator = VitreaCoordinator(hass, mock_vitrea_client, mock_config_entry)

    # Set up some data
    coordinator.data = {
        "01_01": {"platform": "cover", "node": "01", "key": "01"},
        "02_01": {"platform": "switch", "node": "02", "key": "01"},
        "01_02": {"platform": "cover", "node": "01", "key": "02"},
    }

    cover_entities = coordinator.get_entities_by_platform("cover")
    assert len(cover_entities) == 2
    assert "01_01" in cover_entities
    assert "01_02" in cover_entities
    assert "02_01" not in cover_entities


async def test_coordinator_update_existing_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test coordinator updates existing entity data."""
    coordinator = VitreaCoordinator(hass, mock_vitrea_client, mock_config_entry)

    # Track if callback was called
    callback_called = False

    def add_entity_callback(entity_id: str, data: dict) -> None:
        nonlocal callback_called
        callback_called = True

    coordinator.set_entity_add_callback("cover", add_entity_callback)

    # First event - should trigger callback
    mock_event = MagicMock()
    mock_event.node = "01"
    mock_event.key = "01"
    mock_event.status = DeviceStatus.BLIND
    mock_event.data = "050"

    coordinator._handle_status_event(mock_event)
    assert callback_called
    assert coordinator.data["01_01"]["position"] == 50

    # Reset callback flag
    callback_called = False

    # Second event for same entity - should NOT trigger callback
    mock_event.data = "075"
    coordinator._handle_status_event(mock_event)
    assert not callback_called
    assert coordinator.data["01_01"]["position"] == 75


async def test_coordinator_update_data_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test coordinator update returns empty dict when no data."""
    coordinator = VitreaCoordinator(hass, mock_vitrea_client, mock_config_entry)

    # Ensure data is None initially
    assert coordinator.data is None

    # Reset status_request to not trigger callback
    mock_vitrea_client.status_request = AsyncMock()

    # Call _async_update_data - should return empty dict (line 114)
    result = await coordinator._async_update_data()
    assert result == {}
