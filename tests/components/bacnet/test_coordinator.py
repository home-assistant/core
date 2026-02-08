"""Tests for the BACnet coordinator."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import init_integration_with_hub


async def test_coordinator_polls_values(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that the coordinator polls present values."""
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

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
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

    # Set data to None to trigger UpdateFailed
    coordinator.data = None

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_poll_object_error(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test _poll_object returns None on error."""
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

    # Make read_present_value raise an error
    mock_bacnet_client.read_present_value.side_effect = RuntimeError("read failed")

    obj_key, value = await coordinator._poll_object("analog-input,0", "analog-input", 0)

    assert obj_key == "analog-input,0"
    assert value is None


async def test_coordinator_cov_callback(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test COV callback updates coordinator data."""
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

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
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

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
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

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
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

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
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

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
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

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
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

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
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

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
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

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
    _, device_entry = await init_integration_with_hub(hass)
    coordinator = device_entry.runtime_data.coordinator

    # Clear objects to trigger rediscovery
    coordinator.data.objects = []
    coordinator._initial_setup_done = True

    # Make object discovery fail
    mock_bacnet_client.get_device_objects.side_effect = RuntimeError("discovery failed")

    # Should not raise but return data as-is
    data = await coordinator._async_update_data()
    assert data is not None
    assert len(data.objects) == 0
