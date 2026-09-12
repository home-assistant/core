"""Test the Traccar Server integration setup and subscription lifecycle."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytraccar import SubscriptionData, TraccarAuthenticationException, TraccarException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .common import setup_integration

from tests.common import MockConfigEntry, async_capture_events, async_fire_time_changed


async def test_update_data_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    mock_traccar_api_client: AsyncMock,
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
    mock_traccar_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A non-auth error during update should leave setup pending retry."""
    mock_traccar_api_client.get_positions.side_effect = TraccarException(
        "Simulated server error"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_handle_subscription_data_logs_restored_after_failures(
    hass: HomeAssistant,
    mock_traccar_api_client: AsyncMock,
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
            "homeassistant.components.traccar_server.coordinator._SUBSCRIPTION_RECONNECT_DELAY",
            0,
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
    mock_traccar_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Events returned by the Traccar API are imported on schedule and fired on the HA bus."""
    events = async_capture_events(hass, "traccar_device_moving")

    await setup_integration(hass, mock_config_entry)

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["device_traccar_id"] == 0
    assert events[0].data["device_name"] == "X-Wing"
    assert events[0].data["type"] == "deviceMoving"


async def test_subscribe_raises_config_entry_auth_failed(
    hass: HomeAssistant,
    mock_traccar_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An authentication failure must stop retrying, not loop forever."""
    ready_to_raise = asyncio.Event()

    async def _raise_auth_failure_when_ready(_callback: object) -> None:
        await ready_to_raise.wait()
        raise TraccarAuthenticationException("Unauthorized")

    mock_traccar_api_client.subscribe = AsyncMock(
        side_effect=_raise_auth_failure_when_ready
    )

    await setup_integration(hass, mock_config_entry)

    # The background task the integration created is still pending here
    # (it's blocked on ready_to_raise), so it's still tracked on the entry.
    background_tasks = list(mock_config_entry._background_tasks)
    assert len(background_tasks) == 1

    ready_to_raise.set()
    with pytest.raises(ConfigEntryAuthFailed):
        await background_tasks[0]

    # A retryable failure would call subscribe() again after the reconnect
    # delay; an auth failure must not retry at all.
    assert mock_traccar_api_client.subscribe.call_count == 1


async def test_subscribe_retries_on_unexpected_exception(
    hass: HomeAssistant,
    mock_traccar_api_client: AsyncMock,
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
        "homeassistant.components.traccar_server.coordinator._SUBSCRIPTION_RECONNECT_DELAY",
        0,
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert calls == 3
