"""Tests for the BACnet coordinator."""

from __future__ import annotations

import asyncio
import contextlib
import math
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.bacnet.bacnet_client import BACnetObjectInfo
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import MOCK_DEVICE_KEY, create_mock_hub_config_entry, init_integration


async def test_coordinator_polls_values(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that the coordinator polls present values."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # The coordinator should have polled values
    assert coordinator.data is not None
    assert coordinator.data.values is not None
    assert len(coordinator.data.objects) > 0

    # Verify read_present_value was called
    mock_bacnet_client.read_present_value.assert_called()


async def test_coordinator_data_none_raises_update_failed(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that _async_update_data raises UpdateFailed when data is None."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Set data to None to trigger UpdateFailed
    coordinator.data = None

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_poll_object_error(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test _poll_object returns None on error."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Make read_present_value raise an error
    mock_bacnet_client.read_present_value.side_effect = RuntimeError("read failed")

    obj_key, value = await coordinator._poll_object("analog-input,0", "analog-input", 0)

    assert obj_key == "analog-input,0"
    assert value is None


async def test_coordinator_cov_callback(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test COV callback updates coordinator data."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Create a COV callback
    cov_callback = coordinator._make_cov_callback("analog-input", 0)

    # Simulate a COV notification
    cov_callback({"presentValue": 99.5})

    # Check that the value was updated
    assert coordinator._cov_values["analog-input,0"] == 99.5
    assert coordinator.data.values["analog-input,0"] == 99.5


async def test_coordinator_cov_callback_ignores_non_present_value(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test COV callback ignores notifications without presentValue."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Create a COV callback
    cov_callback = coordinator._make_cov_callback("analog-input", 0)

    # Simulate a COV notification without presentValue
    cov_callback({"statusFlags": [False, False, False, False]})

    # Values should not have changed
    assert coordinator._cov_values.get("analog-input,0") is None


async def test_coordinator_setup_cov_subscriptions(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test setting up COV subscriptions."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Reset COV subscriptions
    coordinator._cov_subscription_keys = []

    # Set up COV subscriptions
    await coordinator._setup_cov_subscriptions(coordinator.data.objects)

    # Should have subscribed to COV for supported object types
    assert len(coordinator._cov_subscription_keys) > 0
    mock_bacnet_client.subscribe_cov.assert_called()


async def test_coordinator_setup_cov_subscriptions_error(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test COV subscription errors are handled gracefully."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Make subscribe_cov fail
    mock_bacnet_client.subscribe_cov.side_effect = RuntimeError("COV failed")
    coordinator._cov_subscription_keys = []

    # Should not raise
    await coordinator._setup_cov_subscriptions(coordinator.data.objects)

    # No subscriptions should have been added
    assert len(coordinator._cov_subscription_keys) == 0


async def test_coordinator_update_skips_cov_objects(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that polling skips objects with active COV subscriptions."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Simulate active COV subscription using simple key format
    # The coordinator splits on ":" with maxsplit=1, so the key after the
    # first ":" must match the obj_key format "type,instance"
    coordinator._cov_subscription_keys = ["device:analog-input,0"]
    coordinator._cov_values["analog-input,0"] = 75.0

    # Reset mock to track new calls
    mock_bacnet_client.read_present_value.reset_mock()

    # Trigger update
    await coordinator._async_update_data()

    # Verify analog-input,0 was NOT polled (it has COV)
    for call in mock_bacnet_client.read_present_value.call_args_list:
        assert call.args[1:] != ("analog-input", 0), (
            "Should not poll object with active COV subscription"
        )


async def test_coordinator_background_setup(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test background setup runs and sets initial_setup_done."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # background setup was started in async_setup_entry
    # Wait for it to complete (it does asyncio.sleep(1) first)
    if coordinator._background_setup_task:
        with (
            patch("asyncio.sleep", return_value=None),
            contextlib.suppress(TimeoutError, asyncio.CancelledError),
        ):
            await asyncio.wait_for(
                asyncio.shield(coordinator._background_setup_task), timeout=5
            )


async def test_coordinator_async_shutdown(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test async_shutdown cleans up COV subscriptions."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Add some mock COV subscriptions
    coordinator._cov_subscription_keys = ["sub1", "sub2", "sub3"]

    await coordinator.async_shutdown()

    # All subscriptions should have been unsubscribed
    assert mock_bacnet_client.unsubscribe_cov.call_count >= 3
    assert len(coordinator._cov_subscription_keys) == 0


async def test_coordinator_async_shutdown_handles_errors(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test async_shutdown handles errors during unsubscribe."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Make unsubscribe fail
    mock_bacnet_client.unsubscribe_cov.side_effect = RuntimeError("unsubscribe failed")
    coordinator._cov_subscription_keys = ["sub1"]

    # Should not raise
    await coordinator.async_shutdown()
    assert len(coordinator._cov_subscription_keys) == 0


async def test_coordinator_update_with_poll_error(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that polling errors for individual objects don't stop the update."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Make read_present_value fail for some objects
    call_count = 0

    async def _intermittent_fail(addr, obj_type, obj_inst):
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 0:
            raise RuntimeError("intermittent failure")
        return 42.0

    mock_bacnet_client.read_present_value.side_effect = _intermittent_fail

    # Trigger update - should not raise
    data = await coordinator._async_update_data()
    assert data is not None


async def test_coordinator_object_discovery_error(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test error during object discovery in _async_update_data."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Clear objects to trigger rediscovery
    coordinator.data.objects = []
    coordinator._initial_setup_done = True

    # Make object discovery fail
    mock_bacnet_client.get_device_objects.side_effect = RuntimeError("discovery failed")

    # Should not raise but return data as-is
    data = await coordinator._async_update_data()
    assert data is not None
    assert len(data.objects) == 0


async def test_rediscovery_detects_new_objects(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that re-discovery detects newly added objects."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Mark initial setup done and expire the rediscovery timer
    coordinator._initial_setup_done = True
    coordinator._last_rediscovery = 0  # Expired

    original_count = len(coordinator.data.objects)

    # Return original objects plus a new one on re-discovery
    new_object = BACnetObjectInfo(
        object_type="analog-input",
        object_instance=99,
        object_name="New Sensor",
        present_value=42.0,
        units="degreesCelsius",
    )
    mock_bacnet_client.get_device_objects.return_value = [
        *coordinator.data.objects,
        new_object,
    ]

    # Track callback invocations
    callback_objects: list[BACnetObjectInfo] = []
    coordinator.new_objects_callbacks.append(callback_objects.extend)

    await coordinator._async_update_data()

    assert len(coordinator.data.objects) == original_count + 1
    assert any(obj.object_instance == 99 for obj in coordinator.data.objects)
    assert len(callback_objects) == 1
    assert callback_objects[0].object_name == "New Sensor"


async def test_rediscovery_detects_removed_objects(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that re-discovery detects removed objects and cleans up entities."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Mark initial setup done and expire the rediscovery timer
    coordinator._initial_setup_done = True
    coordinator._last_rediscovery = 0

    # Verify we have sensor entities initially
    entity_registry = er.async_get(hass)
    entries_before = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries_before) > 0

    # Return an empty object list on re-discovery (all removed)
    mock_bacnet_client.get_device_objects.return_value = []

    await coordinator._async_update_data()

    assert len(coordinator.data.objects) == 0

    # Entities for removed objects should be cleaned up from the registry
    entries_after = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    # All device-specific entities should have been removed since all objects are gone
    device_entries = [e for e in entries_after if e.unique_id.startswith("1234-")]
    assert len(device_entries) == 0


async def test_rediscovery_detects_changed_metadata(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that re-discovery detects changed state_text on objects."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator._initial_setup_done = True
    coordinator._last_rediscovery = 0

    # Modify state_text on the multi-state-input object
    updated_objects = []
    for obj in coordinator.data.objects:
        if obj.object_type == "multi-state-input" and obj.object_instance == 0:
            updated_obj = BACnetObjectInfo(
                object_type=obj.object_type,
                object_instance=obj.object_instance,
                object_name=obj.object_name,
                present_value=obj.present_value,
                units=obj.units,
                state_text=["Off", "Heating", "Cooling", "Auto", "Emergency"],
            )
            updated_objects.append(updated_obj)
        else:
            updated_objects.append(obj)

    mock_bacnet_client.get_device_objects.return_value = updated_objects

    await coordinator._async_update_data()

    # Find the updated object in coordinator data
    for obj in coordinator.data.objects:
        if obj.object_type == "multi-state-input" and obj.object_instance == 0:
            assert len(obj.state_text) == 5
            assert "Emergency" in obj.state_text
            break
    else:
        pytest.fail("multi-state-input,0 not found after re-discovery")


async def test_rediscovery_failure_does_not_crash(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that re-discovery failure is handled gracefully."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator._initial_setup_done = True
    coordinator._last_rediscovery = 0
    original_count = len(coordinator.data.objects)

    mock_bacnet_client.get_device_objects.side_effect = RuntimeError("device offline")

    # Should not raise
    data = await coordinator._async_update_data()
    assert data is not None
    # Objects should remain unchanged
    assert len(data.objects) == original_count


async def test_rediscovery_skipped_before_initial_setup(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that re-discovery does not run before initial setup is done."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Ensure initial setup is NOT done
    coordinator._initial_setup_done = False
    coordinator._last_rediscovery = 0

    assert not coordinator._should_rediscover()


async def test_rediscovery_respects_interval(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that re-discovery does not run before the interval has elapsed."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator._initial_setup_done = True
    # Set last rediscovery to "just now" via a large monotonic value
    coordinator._last_rediscovery = math.inf

    assert not coordinator._should_rediscover()


async def test_rediscovery_new_object_creates_entity(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that a newly discovered object creates an entity via callback."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator._initial_setup_done = True
    coordinator._last_rediscovery = 0

    # Start with existing objects plus a brand new binary-input
    new_object = BACnetObjectInfo(
        object_type="binary-input",
        object_instance=99,
        object_name="New Alarm",
        present_value=1,
        units="",
    )
    mock_bacnet_client.get_device_objects.return_value = [
        *coordinator.data.objects,
        new_object,
    ]

    await coordinator._async_update_data()
    await hass.async_block_till_done()

    # The new entity should exist
    state = hass.states.get("binary_sensor.test_hvac_controller_new_alarm")
    assert state is not None


async def test_coordinator_setup_cov_empty_list(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test COV subscription setup with empty object list."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator._cov_subscription_keys = []
    mock_bacnet_client.subscribe_cov.reset_mock()

    await coordinator._setup_cov_subscriptions([])

    mock_bacnet_client.subscribe_cov.assert_not_called()


async def test_coordinator_setup_cov_returns_none(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test COV subscription when subscribe returns None (not supported)."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    mock_bacnet_client.subscribe_cov.side_effect = None
    mock_bacnet_client.subscribe_cov.return_value = None
    coordinator._cov_subscription_keys = []

    await coordinator._setup_cov_subscriptions(coordinator.data.objects[:1])

    assert len(coordinator._cov_subscription_keys) == 0


async def test_coordinator_cleanup_cov_for_removed_objects(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test COV cleanup unsubscribes removed objects."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator._cov_subscription_keys = [
        "addr:analog-input,0",
        "addr:analog-input,1",
        "addr:binary-input,0",
    ]

    await coordinator._cleanup_cov_for_removed_objects(
        {"analog-input,0", "binary-input,0"}
    )

    assert coordinator._cov_subscription_keys == ["addr:analog-input,1"]
    assert mock_bacnet_client.unsubscribe_cov.call_count == 2


async def test_coordinator_cleanup_cov_handles_errors(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test COV cleanup handles unsubscribe errors gracefully."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    mock_bacnet_client.unsubscribe_cov.side_effect = RuntimeError("unsubscribe failed")
    coordinator._cov_subscription_keys = ["addr:analog-input,0"]

    await coordinator._cleanup_cov_for_removed_objects({"analog-input,0"})
    assert len(coordinator._cov_subscription_keys) == 0


async def test_rediscovery_new_objects_filtered_by_selected(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that re-discovery filters new objects by selected_objects."""
    entry = create_mock_hub_config_entry(
        selected_objects=["analog-input,0", "analog-input,1"]
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]
    coordinator._initial_setup_done = True
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    coordinator._last_rediscovery = 0

    new_object = BACnetObjectInfo(
        object_type="analog-input",
        object_instance=99,
        object_name="Unselected Sensor",
        present_value=42.0,
        units="degreesCelsius",
    )

    callback_objects: list[BACnetObjectInfo] = []
    coordinator.new_objects_callbacks.append(callback_objects.extend)

    mock_bacnet_client.get_device_objects.return_value = [
        *coordinator.data.objects,
        new_object,
    ]

    await coordinator._async_update_data()

    # Object added to data but NOT to callback (not in selected_objects)
    assert any(obj.object_instance == 99 for obj in coordinator.data.objects)
    assert len(callback_objects) == 0


async def test_coordinator_object_discovery_with_cov_setup(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test initial object discovery sets up COV when initial_setup_done."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator.data.objects = []
    coordinator._initial_setup_done = True
    mock_bacnet_client.subscribe_cov.reset_mock()

    await coordinator._async_update_data()

    mock_bacnet_client.subscribe_cov.assert_called()


async def test_coordinator_background_setup_no_data(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test background setup handles no data gracefully."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator.data.objects = []
    coordinator._initial_setup_done = False
    coordinator._background_setup_task = None

    await coordinator._background_setup()

    assert not coordinator._initial_setup_done


async def test_coordinator_background_setup_exception(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test background setup handles exceptions gracefully."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    mock_bacnet_client.subscribe_cov.side_effect = Exception("catastrophic")
    coordinator._initial_setup_done = False
    coordinator._background_setup_task = None
    coordinator._cov_subscription_keys = []

    await coordinator._background_setup()


async def test_coordinator_should_rediscover_no_last(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test _should_rediscover returns True when _last_rediscovery is None."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator._initial_setup_done = True
    coordinator._last_rediscovery = None

    assert coordinator._should_rediscover()


async def test_coordinator_poll_exception_handled(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that poll exception during update is handled gracefully."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Make polling fail for all objects
    mock_bacnet_client.read_present_value.side_effect = Exception("read failed")
    # Clear COV values so objects will be polled
    coordinator._cov_values.clear()

    # Refresh should succeed (not raise) even though polls fail
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.data is not None


async def test_coordinator_background_setup_poll_exception(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that poll exception during background setup is handled."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Make polling fail during background setup
    mock_bacnet_client.read_present_value.side_effect = Exception("read failed")
    coordinator._initial_setup_done = False
    coordinator._background_setup_task = None
    coordinator._cov_subscription_keys = []

    await coordinator._background_setup()

    # Should complete without raising
    assert coordinator._initial_setup_done is True
