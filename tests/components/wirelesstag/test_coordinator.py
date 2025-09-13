"""Test Wireless Sensor Tag coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from wirelesstagpy.exceptions import WirelessTagsException

from homeassistant.components.wirelesstag.coordinator import (
    WirelessTagDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_update_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tag_data: dict
) -> None:
    """Test successful coordinator update."""
    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_get_tags = AsyncMock(return_value=mock_tag_data)
        mock_api.async_start_monitoring = AsyncMock()

        coordinator = WirelessTagDataUpdateCoordinator(
            hass, mock_api, mock_config_entry
        )

        result = await coordinator._async_update_data()

        # The coordinator transforms the data, so we need to check the structure
        assert isinstance(result, dict)
        assert len(result) == len(mock_tag_data)
        # Check that data is properly transformed (has 'mac' instead of 'tag_manager_mac')
        assert result["tag_1"]["mac"] == "AA:BB:CC:DD:EE:FF"
        mock_api.async_get_tags.assert_called_once()


async def test_coordinator_update_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator update failure."""
    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_get_tags = AsyncMock(
            side_effect=WirelessTagsException("API Error")
        )

        coordinator = WirelessTagDataUpdateCoordinator(
            hass, mock_api, mock_config_entry
        )

        with pytest.raises(UpdateFailed, match="Error communicating with API"):
            await coordinator._async_update_data()

        mock_api.async_get_tags.assert_called_once()


async def test_coordinator_arm_tag_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tag_data: dict
) -> None:
    """Test successful tag arming."""
    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_arm_tag = AsyncMock(return_value=True)
        mock_api.async_get_tags = AsyncMock(return_value=mock_tag_data)
        mock_api.async_start_monitoring = AsyncMock()

        coordinator = WirelessTagDataUpdateCoordinator(
            hass, mock_api, mock_config_entry
        )
        # Process the data through the coordinator to get proper format
        await coordinator.async_refresh()

        with patch.object(coordinator, "async_request_refresh") as mock_refresh:
            result = await coordinator.async_arm_tag("tag_1", "temperature")

            assert result is True
            mock_api.async_arm_tag.assert_called_once_with(
                "tag_1", "AA:BB:CC:DD:EE:FF", "temperature"
            )
            mock_refresh.assert_called_once()


async def test_coordinator_arm_tag_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tag_data: dict
) -> None:
    """Test tag arming failure."""
    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_arm_tag = AsyncMock(return_value=False)
        mock_api.async_get_tags = AsyncMock(return_value=mock_tag_data)
        mock_api.async_start_monitoring = AsyncMock()

        coordinator = WirelessTagDataUpdateCoordinator(
            hass, mock_api, mock_config_entry
        )
        # Process the data through the coordinator to get proper format
        await coordinator.async_refresh()

        with patch.object(coordinator, "async_request_refresh") as mock_refresh:
            result = await coordinator.async_arm_tag("tag_1", "temperature")

            assert result is False
            mock_api.async_arm_tag.assert_called_once_with(
                "tag_1", "AA:BB:CC:DD:EE:FF", "temperature"
            )
            mock_refresh.assert_not_called()


async def test_coordinator_disarm_tag_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tag_data: dict
) -> None:
    """Test successful tag disarming."""
    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_disarm_tag = AsyncMock(return_value=True)
        mock_api.async_get_tags = AsyncMock(return_value=mock_tag_data)
        mock_api.async_start_monitoring = AsyncMock()

        coordinator = WirelessTagDataUpdateCoordinator(
            hass, mock_api, mock_config_entry
        )
        # Process the data through the coordinator to get proper format
        await coordinator.async_refresh()

        with patch.object(coordinator, "async_request_refresh") as mock_refresh:
            result = await coordinator.async_disarm_tag("tag_1", "temperature")

            assert result is True
            mock_api.async_disarm_tag.assert_called_once_with(
                "tag_1", "AA:BB:CC:DD:EE:FF", "temperature"
            )
            mock_refresh.assert_called_once()


async def test_coordinator_disarm_tag_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tag_data: dict
) -> None:
    """Test tag disarming failure."""
    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_disarm_tag = AsyncMock(return_value=False)
        mock_api.async_get_tags = AsyncMock(return_value=mock_tag_data)
        mock_api.async_start_monitoring = AsyncMock()

        coordinator = WirelessTagDataUpdateCoordinator(
            hass, mock_api, mock_config_entry
        )
        # Process the data through the coordinator to get proper format
        await coordinator.async_refresh()

        with patch.object(coordinator, "async_request_refresh") as mock_refresh:
            result = await coordinator.async_disarm_tag("tag_1", "temperature")

            assert result is False
            mock_api.async_disarm_tag.assert_called_once_with(
                "tag_1", "AA:BB:CC:DD:EE:FF", "temperature"
            )
            mock_refresh.assert_not_called()


async def test_coordinator_monitoring_startup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tag_data: dict
) -> None:
    """Test monitoring is started after first successful data fetch."""
    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_get_tags = AsyncMock(return_value=mock_tag_data)
        mock_api.async_start_monitoring = AsyncMock()

        coordinator = WirelessTagDataUpdateCoordinator(
            hass, mock_api, mock_config_entry
        )

        # First call should start monitoring
        await coordinator._async_update_data()
        mock_api.async_start_monitoring.assert_called_once()

        # Second call should not start monitoring again
        await coordinator._async_update_data()
        mock_api.async_start_monitoring.assert_called_once()  # Still only called once


async def test_coordinator_push_callback_handling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tag_data: dict
) -> None:
    """Test push callback handling."""
    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_get_tags = AsyncMock(return_value=mock_tag_data)
        mock_api.async_start_monitoring = AsyncMock()

        coordinator = WirelessTagDataUpdateCoordinator(
            hass, mock_api, mock_config_entry
        )

        # Trigger the monitoring setup
        await coordinator._async_update_data()

        # Get the callback function that was passed to start_monitoring
        mock_api.async_start_monitoring.assert_called_once()
        callback = mock_api.async_start_monitoring.call_args[0][0]

        # Test the callback function - it now schedules an async task
        test_data = {"test": "data"}
        with patch.object(coordinator, "async_refresh") as mock_refresh:
            callback(test_data)
            # Wait for any scheduled tasks to complete
            await hass.async_block_till_done()
            mock_refresh.assert_called_once()


async def test_coordinator_stale_device_removal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_tag_data: dict,
) -> None:
    """Test that stale devices are removed when tags are no longer present."""
    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_start_monitoring = AsyncMock()

        # Create a test device in the registry
        mock_config_entry.add_to_hass(hass)
        device_entry = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={("wirelesstag", "stale_tag_id")},
            name="Stale Tag Device",
            manufacturer="Wireless Sensor Tags",
        )

        coordinator = WirelessTagDataUpdateCoordinator(
            hass, mock_api, mock_config_entry
        )

        # First update with normal data (should not remove device as it's not in current tags)
        mock_api.async_get_tags = AsyncMock(return_value=mock_tag_data)
        await coordinator._async_update_data()

        # Verify the stale device was removed
        updated_device = device_registry.async_get(device_entry.id)
        assert (
            updated_device is None
            or mock_config_entry.entry_id not in updated_device.config_entries
        )

        # Verify current devices from mock_tag_data are not affected
        remaining_devices = dr.async_entries_for_config_entry(
            device_registry, mock_config_entry.entry_id
        )
        # Should have removed the stale device but not affected existing ones
        assert (
            len(remaining_devices) == 0
        )  # Only the stale device was created in this test


async def test_coordinator_dynamic_device_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_tag_data: dict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that new devices are detected and logged when new tags appear."""
    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_start_monitoring = AsyncMock()

        # Initial tag data with one tag
        initial_tag_data = {
            "tag_1": {
                "uuid": "tag_1",
                "is_alive": True,
                "mac": "AA:BB:CC:DD:EE:FF",
                "name": "Living Room",
            }
        }
        mock_api.async_get_tags = AsyncMock(return_value=initial_tag_data)

        mock_config_entry.add_to_hass(hass)

        coordinator = WirelessTagDataUpdateCoordinator(
            hass, mock_api, mock_config_entry
        )

        # First update with initial data (should NOT log new devices)
        await coordinator.async_refresh()

        # Verify no new tag detection was logged on initial update
        assert "Detected new tags:" not in caplog.text

        # Clear logs for second test
        caplog.clear()

        # Update tag data to include a new tag
        updated_tag_data = {
            **initial_tag_data,
            "tag_2": {
                "uuid": "tag_2",
                "is_alive": True,
                "mac": "11:22:33:44:55:66",
                "name": "Bedroom",
            },
        }

        mock_api.async_get_tags = AsyncMock(return_value=updated_tag_data)

        # Second update with new tag data (should log new devices)
        await coordinator.async_refresh()

        # Verify only the new tag was detected
        assert "Detected new tags: tag_2 - adding entities dynamically" in caplog.text


async def test_coordinator_dynamic_device_callbacks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that dynamic device callbacks are properly invoked."""
    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_start_monitoring = AsyncMock()

        # Initial tag data with one tag
        initial_tag_data = {
            "tag_1": {
                "uuid": "tag_1",
                "is_alive": True,
                "mac": "AA:BB:CC:DD:EE:FF",
                "name": "Living Room",
            }
        }
        mock_api.async_get_tags = AsyncMock(return_value=initial_tag_data)

        mock_config_entry.add_to_hass(hass)

        coordinator = WirelessTagDataUpdateCoordinator(
            hass, mock_api, mock_config_entry
        )

        # Register a mock callback
        mock_callback = Mock()
        coordinator.new_devices_callbacks.append(mock_callback)

        # First update with initial data (should not call callback)
        await coordinator.async_refresh()
        mock_callback.assert_not_called()

        # Update tag data to include a new tag
        updated_tag_data = {
            **initial_tag_data,
            "tag_2": {
                "uuid": "tag_2",
                "is_alive": True,
                "mac": "11:22:33:44:55:66",
                "name": "Bedroom",
            },
        }
        mock_api.async_get_tags = AsyncMock(return_value=updated_tag_data)

        # Second update with new tag data (should call callback)
        await coordinator.async_refresh()

        # Verify callback was called with the new tag ID
        mock_callback.assert_called_once_with({"tag_2"})
