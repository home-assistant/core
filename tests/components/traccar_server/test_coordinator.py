"""Test the Traccar Server coordinator."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Generator
from datetime import timedelta
import logging
import sys
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytraccar import SubscriptionData, TraccarAuthenticationException, TraccarException

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util

from .common import setup_integration

from tests.common import MockConfigEntry, async_capture_events, async_fire_time_changed


def _get_subscription_callback(
    mock_traccar_api_client: AsyncMock,
) -> Callable[[SubscriptionData], Awaitable[None]]:
    """Return the callback our integration registered with client.subscribe().

    Reading it off the mock's call args exercises the exact function
    pytraccar would invoke, instead of calling a coordinator method by name.
    """
    return mock_traccar_api_client.subscribe.call_args.args[0]


async def test_update_data_happy_path(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Devices, positions, and geofences merged by the coordinator reach the device tracker."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("device_tracker.x_wing")
    assert state is not None
    assert state.attributes["latitude"] == 52.0
    assert state.attributes["longitude"] == 25.0
    assert state.attributes["gps_accuracy"] == 3.5
    # accuracy (3.5) is below max_accuracy (5.0), so the custom attribute
    # should be included rather than filtered out.
    assert state.attributes["custom_attr_1"] == "custom_attr_1_value"


async def test_update_data_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """An auth failure during update should fail setup and prompt reauth."""
    mock_traccar_api_client.get_devices.side_effect = TraccarAuthenticationException(
        "Unauthorized"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        flow["context"]["source"] == "reauth"
        for flow in hass.config_entries.flow.async_progress()
    )


async def test_update_data_traccar_exception_retries_setup(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """A non-auth error during update should leave setup pending retry."""
    mock_traccar_api_client.get_positions.side_effect = TraccarException(
        "Simulated server error"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_handle_subscription_data_updates_known_device(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """A subscription update for a known device updates its device tracker state."""
    await setup_integration(hass, mock_config_entry)
    subscription_callback = _get_subscription_callback(mock_traccar_api_client)

    updated_position = {
        "id": 0,
        "deviceId": 0,
        "latitude": 60.0,
        "longitude": 30.0,
        "accuracy": 3.5,
        "address": "Mos Eisley",
        "attributes": {"custom_attr_1": "custom_attr_1_value"},
    }

    await subscription_callback(
        {"devices": None, "events": None, "positions": [updated_position]}
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.x_wing")
    assert state.attributes["latitude"] == 60.0
    assert state.attributes["longitude"] == 30.0


async def test_handle_subscription_data_ignores_unknown_device(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Subscription data for a device we haven't seen via polling is ignored."""
    await setup_integration(hass, mock_config_entry)
    subscription_callback = _get_subscription_callback(mock_traccar_api_client)

    state_before = hass.states.get("device_tracker.x_wing")

    unknown_position = {
        "id": 999,
        "deviceId": 999,
        "latitude": 60.0,
        "longitude": 30.0,
        "accuracy": 3.5,
        "address": "Mos Eisley",
        "attributes": {},
    }

    # Should not raise, and should not touch the known device's state.
    await subscription_callback(
        {"devices": None, "events": None, "positions": [unknown_position]}
    )
    await hass.async_block_till_done()

    state_after = hass.states.get("device_tracker.x_wing")
    assert state_after.state == state_before.state
    assert state_after.attributes == state_before.attributes
    assert hass.states.get("device_tracker.unknown_999") is None


async def test_handle_subscription_data_filters_low_accuracy_position(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """A position update that fails the accuracy filter is skipped."""
    await setup_integration(hass, mock_config_entry)
    subscription_callback = _get_subscription_callback(mock_traccar_api_client)

    original_latitude = hass.states.get("device_tracker.x_wing").attributes["latitude"]

    poor_accuracy_position = {
        "id": 0,
        "deviceId": 0,
        "latitude": 60.0,
        "longitude": 30.0,
        # max_accuracy for this config entry is 5.0.
        "accuracy": 999.0,
        "address": "Should not be applied",
        "attributes": {"custom_attr_1": "custom_attr_1_value"},
    }

    await subscription_callback(
        {"devices": None, "events": None, "positions": [poor_accuracy_position]}
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.x_wing")
    assert state.attributes["latitude"] == original_latitude


async def test_handle_subscription_data_logs_restored_after_failures(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Receiving data after failures logs a restored message and resets the counter."""
    calls = 0

    async def _fail_three_times_then_succeed(
        callback: Callable[[SubscriptionData], Awaitable[None]],
    ) -> None:
        nonlocal calls
        calls += 1
        if calls <= 3:
            raise TraccarException("Simulated dropped connection")
        await callback({"devices": None, "events": None, "positions": None})
        raise asyncio.CancelledError

    mock_traccar_api_client.subscribe = AsyncMock(
        side_effect=_fail_three_times_then_succeed
    )

    with (
        patch(
            "homeassistant.components.traccar_server.coordinator.asyncio.sleep",
            new=AsyncMock(),
        ),
        caplog.at_level(logging.INFO, logger="homeassistant.components.traccar_server"),
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done(wait_background_tasks=True)

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert any(
        "connection restored after 3 failed attempt(s)" in r.message
        for r in info_records
    )


async def test_import_events_fires_hass_events(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Events returned by the Traccar API are imported on schedule and fired on the HA bus."""
    events = async_capture_events(hass, "traccar_device_moving")

    await setup_integration(hass, mock_config_entry)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["device_traccar_id"] == 0
    assert events[0].data["device_name"] == "X-Wing"
    assert events[0].data["type"] == "deviceMoving"


async def test_subscribe_raises_config_entry_auth_failed(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """An authentication failure must stop retrying, not loop forever."""
    mock_traccar_api_client.subscribe = AsyncMock(
        side_effect=TraccarAuthenticationException("Unauthorized")
    )

    background_tasks: list[asyncio.Task] = []
    original_create_background_task = ConfigEntry.async_create_background_task

    def _capture_background_task(
        self: ConfigEntry,
        hass: HomeAssistant,
        target: Coroutine[Any, Any, Any],
        name: str,
        eager_start: bool = True,
    ) -> asyncio.Task:
        task = original_create_background_task(self, hass, target, name, eager_start)
        background_tasks.append(task)
        return task

    with patch.object(
        ConfigEntry, "async_create_background_task", _capture_background_task
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(background_tasks) == 1
    with pytest.raises(ConfigEntryAuthFailed):
        background_tasks[0].result()

    # A retryable failure would call subscribe() again after sleep(10);
    # an auth failure must not retry at all.
    assert mock_traccar_api_client.subscribe.call_count == 1


async def test_subscribe_does_not_recurse_across_reconnects(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Subscribe retries must not grow the call stack."""
    attempts = 0
    target_attempts = sys.getrecursionlimit() * 2

    async def _flaky_subscribe(_callback: object) -> None:
        nonlocal attempts
        attempts += 1
        if attempts >= target_attempts:
            # End the task deterministically, the same way an unload would.
            raise asyncio.CancelledError
        raise TraccarException("Simulated dropped connection")

    mock_traccar_api_client.subscribe = AsyncMock(side_effect=_flaky_subscribe)

    with patch(
        "homeassistant.components.traccar_server.coordinator.asyncio.sleep",
        new=AsyncMock(),
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert attempts == target_attempts


async def test_subscribe_does_not_busy_loop_on_clean_return(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """If client.subscribe() ever returns without raising, still throttle.

    pytraccar's subscribe() should always raise on disconnect (see
    pytraccar#477), so a clean return isn't expected in practice. But the
    retry loop must not assume that - if it ever happens, reconnecting
    immediately with no delay would spin the event loop at 100% CPU.
    """
    calls = 0

    async def _clean_return_then_cancel(_callback: object) -> None:
        nonlocal calls
        calls += 1
        if calls >= 3:
            raise asyncio.CancelledError

    mock_traccar_api_client.subscribe = AsyncMock(side_effect=_clean_return_then_cancel)

    with patch(
        "homeassistant.components.traccar_server.coordinator.asyncio.sleep",
        new=AsyncMock(),
    ) as mock_sleep:
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert calls == 3
    # Only calls 1 and 2 (the clean returns) reach the loop's sleep(10);
    # call 3 raises CancelledError before that line, so exactly two real
    # reconnect delays are attributable to this code path.
    ten_second_sleeps = [
        call for call in mock_sleep.await_args_list if call.args == (10,)
    ]
    assert len(ten_second_sleeps) == 2


async def test_subscribe_retries_on_unexpected_exception(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """An exception that isn't a TraccarException must still be retried.

    pytraccar's own exceptions all subclass TraccarException, but an
    unrecognized failure could still slip through as something else -
    that must not be allowed to escape the retry loop.
    """
    calls = 0

    async def _weird_failure_then_cancel(_callback: object) -> None:
        nonlocal calls
        calls += 1
        if calls >= 3:
            raise asyncio.CancelledError
        # Something that is NOT a TraccarException - e.g. a raw error
        # that slipped through pytraccar's own exception wrapping.
        raise ValueError("Simulated unexpected failure")

    mock_traccar_api_client.subscribe = AsyncMock(
        side_effect=_weird_failure_then_cancel
    )

    with patch(
        "homeassistant.components.traccar_server.coordinator.asyncio.sleep",
        new=AsyncMock(),
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert calls == 3


async def test_subscribe_logs_error_once_then_periodic_reminder(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The first failure logs an error; later failures throttle to a periodic warning."""
    calls = 0
    target_attempts = 61  # Crosses two 30-attempt reminder boundaries (30, 60).

    async def _always_fails(_callback: object) -> None:
        nonlocal calls
        calls += 1
        if calls >= target_attempts:
            raise asyncio.CancelledError
        raise TraccarException("Simulated dropped connection")

    mock_traccar_api_client.subscribe = AsyncMock(side_effect=_always_fails)

    with (
        patch(
            "homeassistant.components.traccar_server.coordinator.asyncio.sleep",
            new=AsyncMock(),
        ),
        caplog.at_level(logging.INFO, logger="homeassistant.components.traccar_server"),
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done(wait_background_tasks=True)

    error_records = [
        r
        for r in caplog.records
        if r.levelno == logging.ERROR
        and r.name == "homeassistant.components.traccar_server"
    ]
    warning_records = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and r.name == "homeassistant.components.traccar_server"
    ]

    assert len(error_records) == 1
    assert "Error while subscribing to Traccar" in error_records[0].message
    assert len(warning_records) == 2
    assert all(
        "Still unable to (re)connect to Traccar" in r.message for r in warning_records
    )
    assert any("60" in r.message for r in warning_records)


async def test_subscribe_clean_return_resets_error_logging(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A clean return re-arms error logging for the next failure streak.

    The should-log flag must reset alongside the failure counter - otherwise
    a failure streak starting right after a clean return would be silently
    throttled instead of logging its first error.
    """
    calls = 0

    async def _fail_then_clean_return_then_fail(_callback: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TraccarException("First failure")
        if calls == 2:
            return  # Clean return - should re-arm error logging.
        if calls == 3:
            raise TraccarException("Second failure, after clean return")
        raise asyncio.CancelledError

    mock_traccar_api_client.subscribe = AsyncMock(
        side_effect=_fail_then_clean_return_then_fail
    )

    with (
        patch(
            "homeassistant.components.traccar_server.coordinator.asyncio.sleep",
            new=AsyncMock(),
        ),
        caplog.at_level(logging.INFO, logger="homeassistant.components.traccar_server"),
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done(wait_background_tasks=True)

    error_records = [
        r
        for r in caplog.records
        if r.levelno == logging.ERROR
        and r.name == "homeassistant.components.traccar_server"
    ]
    assert len(error_records) == 2
    assert "First failure" in error_records[0].message
    assert "Second failure, after clean return" in error_records[1].message
