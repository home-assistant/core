"""Test FMD device tracker high frequency mode and concurrency."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.fmd.common import setup_integration


async def test_device_tracker_high_frequency_mode(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test high frequency mode switch."""
    await setup_integration(hass, mock_fmd_api)

    # Turn on high frequency mode
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_high_frequency_mode"},
        blocking=True,
    )

    state = hass.states.get("switch.fmd_test_user_high_frequency_mode")
    assert state.state == "on"

    # Verify location request is called
    await hass.async_block_till_done()
    mock_fmd_api.create.return_value.request_location.assert_called()


async def test_device_tracker_high_frequency_mode_success_path(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test high frequency mode success path with location request and sleep."""
    # Mock request_location to return True
    mock_fmd_api.create.return_value.request_location.return_value = True

    # Mock get_locations for the update after sleep
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "gps",
        }
    ]

    await setup_integration(hass, mock_fmd_api)

    # Enable high frequency mode
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_high_frequency_mode"},
        blocking=True,
    )

    await hass.async_block_till_done()

    # Verify request_location was called
    mock_fmd_api.create.return_value.request_location.assert_called()


async def test_device_tracker_high_frequency_error_handling(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test error handling during high frequency poll."""
    await setup_integration(hass, mock_fmd_api)

    tracker = hass.config_entries.async_entries("fmd")[0].runtime_data.tracker

    # Enable high frequency mode manually
    tracker._high_frequency_mode = True

    # Mock request_location to raise an exception
    mock_fmd_api.create.return_value.request_location.side_effect = Exception(
        "Test Error"
    )

    # Capture the callback
    with patch(
        "homeassistant.components.fmd.device_tracker.async_track_time_interval"
    ) as mock_track:
        tracker.start_polling()
        callback = mock_track.call_args[0][1]

        # Call the callback
        # It should catch the exception and log error, then proceed to async_update
        with patch.object(tracker, "async_update") as mock_update:
            await callback()

            # Verify async_update WAS called (it proceeds after error)
            mock_update.assert_called_once()

    # Also test the "else" branch where request_location returns False
    mock_fmd_api.create.return_value.request_location.side_effect = None
    mock_fmd_api.create.return_value.request_location.return_value = False

    with patch(
        "homeassistant.components.fmd.device_tracker.async_track_time_interval"
    ) as mock_track:
        tracker.start_polling()
        callback = mock_track.call_args[0][1]

        with patch.object(tracker, "async_update") as mock_update:
            await callback()
            mock_update.assert_called_once()


async def test_device_tracker_update_locations_reentrancy(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test update_locations skips if already updating."""
    await setup_integration(hass, mock_fmd_api)

    tracker = hass.config_entries.async_entries("fmd")[0].runtime_data.tracker

    # Manually set _is_updating to True
    tracker._is_updating = True

    with patch(
        "homeassistant.components.fmd.device_tracker.async_track_time_interval"
    ) as mock_track:
        tracker.start_polling()
        callback = mock_track.call_args[0][1]

        # Call the callback while _is_updating is True
        # We need to mock async_update to verify it wasn't called
        with patch.object(tracker, "async_update") as mock_update:
            await callback()
            mock_update.assert_not_called()


async def test_device_tracker_poll_skip_when_already_updating(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog
) -> None:
    """When update is already in progress, scheduled poll logs warning and skips."""
    await setup_integration(hass, mock_fmd_api)

    # Get the tracker
    entry = hass.config_entries.async_entries("fmd")[0]
    tracker = entry.runtime_data.tracker

    # Manually set _is_updating to True to simulate ongoing update
    tracker._is_updating = True

    # Mock async_update to verify it's not called
    with patch.object(tracker, "async_update") as mock_update:
        # Advance time to trigger the scheduled poll
        # The polling interval is 30 minutes by default
        next_update = dt_util.now() + timedelta(minutes=30)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

        # Verify async_update was NOT called
        mock_update.assert_not_called()

    # Verify warning was logged
    assert any(
        "Previous update still in progress" in record.message
        for record in caplog.records
    )


async def test_device_tracker_high_frequency_initial_request_returns_false(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog
) -> None:
    """High-frequency mode poll with request_location returning False logs warning."""
    await setup_integration(hass, mock_fmd_api)

    # Get the tracker
    entry = hass.config_entries.async_entries("fmd")[0]
    tracker = entry.runtime_data.tracker

    # Enable high-frequency mode first
    await tracker.set_high_frequency_mode(True)

    # Mock request_location to return False (failure during poll)
    mock_fmd_api.create.return_value.request_location.return_value = False

    caplog.clear()

    # Advance time to trigger the scheduled poll
    # High frequency interval is 5 minutes by default
    # Add a small buffer to ensure the timer fires
    next_update = dt_util.now() + timedelta(minutes=5, seconds=1)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    # Verify request_location was called
    mock_fmd_api.create.return_value.request_location.assert_called()

    # Verify warning was logged
    assert any(
        "Failed to request location from device" in record.message
        for record in caplog.records
    )


async def test_device_tracker_high_frequency_poll_request_failure_logs_error(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog
) -> None:
    """During high-frequency polling, request_location failure logs error."""
    await setup_integration(hass, mock_fmd_api)

    # Get the tracker
    entry = hass.config_entries.async_entries("fmd")[0]
    tracker = entry.runtime_data.tracker

    # Enable high-frequency mode first (with successful initial request)
    mock_fmd_api.create.return_value.request_location.return_value = True
    await tracker.set_high_frequency_mode(True)

    # Now mock request_location to raise exception during poll
    mock_fmd_api.create.return_value.request_location.side_effect = RuntimeError(
        "network failure"
    )

    caplog.clear()

    # Advance time to trigger the scheduled poll
    # Add a small buffer to ensure the timer fires
    next_update = dt_util.now() + timedelta(minutes=5, seconds=1)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    # Verify error was logged
    assert any(
        "Error requesting location during high-frequency poll" in record.message
        for record in caplog.records
    )


async def test_high_frequency_request_provider_mapping(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """When high frequency is enabled, selected provider maps to the API request provider."""
    await setup_integration(hass, mock_fmd_api)

    # Get the tracker
    entry = hass.config_entries.async_entries("fmd")[0]
    tracker = entry.runtime_data.tracker

    # Set the location source to GPS Only (Accurate) so provider should be 'gps'
    hass.states.async_set("select.fmd_test_user_location_source", "GPS Only (Accurate)")
    await hass.async_block_till_done()

    # Patch sleep to avoid waiting and ensure request_location returns True
    mock_api = mock_fmd_api.create.return_value
    mock_api.request_location.return_value = True

    # Force high frequency mode and patch the async_track_time_interval so the
    # update callback is executed immediately (to exercise provider mapping).
    def _fake_async_track(hass_obj, callback, interval):
        hass_obj.async_create_task(callback(None))
        return lambda: None

    with (
        patch(
            "homeassistant.components.fmd.device_tracker.async_track_time_interval",
            side_effect=_fake_async_track,
        ),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        tracker._high_frequency_mode = True
        tracker.start_polling()
        await hass.async_block_till_done()

    # request_location should have been called with provider 'gps'
    # Confirm the mock was awaited with provider 'gps' (it may be called multiple times)
    calls = mock_api.request_location.await_args_list
    assert any(kwargs.get("provider") == "gps" for _, kwargs in calls)


async def test_set_high_frequency_interval_applies_immediately_when_enabled(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Updating the high-frequency interval while enabled applies immediately."""
    await setup_integration(hass, mock_fmd_api)

    entry = hass.config_entries.async_entries("fmd")[0]
    tracker = entry.runtime_data.tracker

    # Enable high frequency mode
    tracker._high_frequency_mode = True
    original_interval = tracker._polling_interval

    # Update the high-frequency interval - should apply to polling interval immediately
    tracker.set_high_frequency_interval(2)
    assert tracker._high_frequency_interval == 2
    assert tracker._polling_interval == 2
    assert tracker._polling_interval != original_interval


async def test_device_tracker_polling_interval_update(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker polling interval can be updated."""
    await setup_integration(hass, mock_fmd_api)

    entry = hass.config_entries.async_entries("fmd")[0]
    tracker = entry.runtime_data.tracker

    # Update polling interval
    tracker.set_polling_interval(10)
    await hass.async_block_till_done()

    assert tracker.polling_interval == 10


async def test_device_tracker_high_frequency_mode_toggle(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker high frequency mode can be toggled."""
    await setup_integration(hass, mock_fmd_api)

    # Get the entity and toggle high frequency mode
    entry = hass.config_entries.async_entries("fmd")[0]
    tracker = entry.runtime_data.tracker

    # Enable high frequency mode
    await tracker.set_high_frequency_mode(True)
    await hass.async_block_till_done()

    # Disable high frequency mode
    await tracker.set_high_frequency_mode(False)
    await hass.async_block_till_done()

    # Verify the method was called (implicit by no error)
    assert tracker is not None


async def test_device_tracker_polling_interval_switch(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test switching between normal and high-frequency polling intervals."""
    await setup_integration(hass, mock_fmd_api)

    tracker = hass.config_entries.async_entries("fmd")[0].runtime_data.tracker
    # Initial interval should be normal
    assert tracker.polling_interval == tracker._normal_interval

    # Set high-frequency interval and enable high-frequency mode
    tracker.set_high_frequency_interval(1)
    await tracker.set_high_frequency_mode(True)
    assert tracker.polling_interval == 1

    # Disable high-frequency mode, should revert to normal
    await tracker.set_high_frequency_mode(False)
    assert tracker.polling_interval == tracker._normal_interval


async def test_high_frequency_mode_request_location_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """set_high_frequency_mode handles request_location exceptions."""
    await setup_integration(hass, mock_fmd_api)

    tracker = hass.config_entries.async_entries("fmd")[0].runtime_data.tracker
    # Make API raise during request
    tracker.api.request_location = AsyncMock(side_effect=RuntimeError("boom"))

    # Should not raise
    await tracker.set_high_frequency_mode(True)
    # Disable again to restore interval
    await tracker.set_high_frequency_mode(False)


async def test_device_tracker_high_frequency_interval_boundary(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test high frequency mode with interval at boundary values."""
    await setup_integration(hass, mock_fmd_api)

    # Get the tracker
    entry = hass.config_entries.async_entries("fmd")[0]
    tracker = entry.runtime_data.tracker

    # Enable high frequency mode
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_high_frequency_mode"},
        blocking=True,
    )

    # Set interval to minimum (1 minute)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.fmd_test_user_high_frequency_interval", "value": 1},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify interval was updated
    assert tracker._high_frequency_interval == 1
