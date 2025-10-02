"""Tests for the OpenRGB coordinator."""

from unittest.mock import MagicMock

from openrgb.utils import OpenRGBDisconnected

from homeassistant.components.openrgb.coordinator import OpenRGBCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_reconnection_on_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
) -> None:
    """Test that coordinator reconnects when update fails."""
    mock_config_entry.add_to_hass(hass)

    # Set up the coordinator
    coordinator = OpenRGBCoordinator(hass, mock_config_entry)
    await coordinator._async_setup()

    # Simulate the first update call failing, then second succeeding
    mock_openrgb_client.update.side_effect = [
        OpenRGBDisconnected(),
        None,  # Second call succeeds after reconnect
    ]

    # First update should trigger reconnection logic
    await coordinator.async_refresh()

    # Verify that disconnect and connect were called (reconnection happened)
    mock_openrgb_client.disconnect.assert_called_once()
    mock_openrgb_client.connect.assert_called_once()

    # Verify that update was called twice (once failed, once after reconnect)
    assert mock_openrgb_client.update.call_count == 2

    # Verify that the coordinator has data after successful reconnect
    assert coordinator.data is not None
    assert len(coordinator.data) > 0


async def test_reconnection_fails_second_attempt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
) -> None:
    """Test that coordinator fails when reconnection also fails."""
    mock_config_entry.add_to_hass(hass)

    # Set up the coordinator
    coordinator = OpenRGBCoordinator(hass, mock_config_entry)
    await coordinator._async_setup()

    # Simulate the first update call failing, and reconnection also failing
    mock_openrgb_client.update.side_effect = [
        OpenRGBDisconnected(),
        None,  # Second call would succeed, but we simulate failure on reconnect
    ]

    # Simulate connect raising an exception to mimic failed reconnection
    mock_openrgb_client.connect.side_effect = ConnectionRefusedError()

    # Update should fail after failed reconnection attempt
    await coordinator.async_refresh()

    # Verify that the update failed
    assert coordinator.last_update_success is False

    # Verify that disconnect and connect were called (reconnection was attempted)
    mock_openrgb_client.disconnect.assert_called_once()
    mock_openrgb_client.connect.assert_called_once()

    # Verify that update was only called in the first attempt
    mock_openrgb_client.update.assert_called_once()


async def test_normal_update_without_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
) -> None:
    """Test that normal updates work without triggering reconnection."""
    mock_config_entry.add_to_hass(hass)

    # Set up the coordinator
    coordinator = OpenRGBCoordinator(hass, mock_config_entry)
    await coordinator._async_setup()

    # Simulate successful update
    mock_openrgb_client.update.side_effect = None
    mock_openrgb_client.update.return_value = None

    # Update should succeed
    await coordinator.async_refresh()

    # Verify that disconnect and connect were NOT called (no reconnection needed)
    mock_openrgb_client.disconnect.assert_not_called()
    mock_openrgb_client.connect.assert_not_called()

    # Verify that update was called only once
    mock_openrgb_client.update.assert_called_once()

    # Verify that the coordinator has data
    assert coordinator.data is not None
    assert len(coordinator.data) > 0
