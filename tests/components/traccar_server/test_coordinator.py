"""Test the Traccar Server coordinator."""

import asyncio
from collections.abc import Awaitable, Callable, Generator
import logging
import sys
from unittest.mock import AsyncMock, patch

import pytest
from pytraccar import SubscriptionData, TraccarAuthenticationException, TraccarException

from homeassistant.components.traccar_server.coordinator import TraccarServerCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .common import setup_integration

from tests.common import MockConfigEntry, async_capture_events


async def _setup_and_isolate_coordinator(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> TraccarServerCoordinator:
    """Set up the entry, then detach the coordinator from real-time use.

    async_setup_entry() starts a background task that also calls
    subscribe(); unloading cancels that task so a test can await
    coordinator.subscribe() directly without racing it.
    """
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    return coordinator


async def test_update_data_happy_path(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Devices, positions, and geofences are merged into coordinator data."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert 0 in coordinator.data

    entry = coordinator.data[0]
    assert entry["device"]["name"] == "X-Wing"
    assert entry["position"]["id"] == 0
    assert entry["geofence"]["name"] == "Tatooine"
    # accuracy (3.5) is below max_accuracy (5.0), so the custom attribute
    # should be included rather than filtered out.
    assert entry["attributes"]["custom_attr_1"] == "custom_attr_1_value"


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
    """A subscription update for a known device updates coordinator data."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    signals: list[str] = []
    async_dispatcher_connect(
        hass, f"{mock_config_entry.domain}_0", lambda: signals.append("0")
    )

    updated_position = dict(coordinator.data[0]["position"])
    updated_position["address"] = "Mos Eisley"

    await coordinator.handle_subscription_data(
        {"devices": None, "events": None, "positions": [updated_position]}
    )

    assert coordinator.data[0]["position"]["address"] == "Mos Eisley"
    assert signals == ["0"]


async def test_handle_subscription_data_ignores_unknown_device(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Subscription data for a device we haven't seen via polling is ignored."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    before = dict(coordinator.data)

    unknown_position = dict(coordinator.data[0]["position"])
    unknown_position["deviceId"] = 999
    unknown_position["id"] = 999

    # Should not raise, and should not touch existing data.
    await coordinator.handle_subscription_data(
        {"devices": None, "events": None, "positions": [unknown_position]}
    )

    assert coordinator.data.keys() == before.keys()
    assert coordinator.data[0] == before[0]


async def test_handle_subscription_data_filters_low_accuracy_position(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """A position update that fails the accuracy filter is skipped."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    original_address = coordinator.data[0]["position"]["address"]

    poor_accuracy_position = dict(coordinator.data[0]["position"])
    poor_accuracy_position["address"] = "Should not be applied"
    # max_accuracy for this config entry is 5.0.
    poor_accuracy_position["accuracy"] = 999.0

    await coordinator.handle_subscription_data(
        {"devices": None, "events": None, "positions": [poor_accuracy_position]}
    )

    assert coordinator.data[0]["position"]["address"] == original_address


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
    """Events returned by the Traccar API are fired on the HA bus."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    events = async_capture_events(hass, "traccar_device_moving")

    await coordinator.import_events(None)
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
    """Authentication failures should stop retrying and bubble up.

    The side_effect must be installed after isolating the coordinator -
    otherwise the still-running setup background task would hit it
    first and fail with an unretrieved exception of its own.
    """
    coordinator = await _setup_and_isolate_coordinator(hass, mock_config_entry)

    async def _unauthorized_subscribe(_callback: object) -> None:
        raise TraccarAuthenticationException("Unauthorized")

    mock_traccar_api_client.subscribe = AsyncMock(side_effect=_unauthorized_subscribe)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.subscribe()


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
