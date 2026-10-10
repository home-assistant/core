"""Tests for the GARDENA smart local coordinator."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from gardena_smart_local_api.messages import (
    ErrorMessage,
    ErrorMetadata,
    IngressMessageList,
)
import pytest

from homeassistant.components.gardena_smart_local.const import DEFAULT_PORT, DOMAIN
from homeassistant.components.gardena_smart_local.coordinator import (
    GardenaSmartLocalCoordinator,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_PASSWORD: "testpassword",
}


@pytest.fixture
def coordinator(hass: HomeAssistant) -> GardenaSmartLocalCoordinator:
    """Return a coordinator that is not connected to a gateway."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    return GardenaSmartLocalCoordinator(
        hass,
        entry,
        MOCK_DATA[CONF_HOST],
        MOCK_DATA[CONF_PORT],
        MOCK_DATA[CONF_PASSWORD],
    )


async def test_schedule_unknown_device_discovery_debounces_burst(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A burst of events for unknown devices schedules only one re-discovery run."""
    with patch.object(coordinator.hass.loop, "call_later") as call_later:
        coordinator._schedule_unknown_device_discovery("dev-1")
        coordinator._schedule_unknown_device_discovery("dev-1")
        coordinator._schedule_unknown_device_discovery("dev-2")

    call_later.assert_called_once()
    assert coordinator._unknown_device_discovery_handle is not None


async def test_schedule_unknown_device_discovery_skips_including_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device this coordinator is actively including must not auto-discover."""
    coordinator._including_device_ids.add("dev-1")

    with patch.object(coordinator.hass.loop, "call_later") as call_later:
        coordinator._schedule_unknown_device_discovery("dev-1")

    call_later.assert_not_called()
    assert coordinator._unknown_device_discovery_handle is None


async def test_discover_unknown_devices_runs_full_discovery(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The debounced run re-discovers and clears its handle when done."""
    coordinator._unknown_device_discovery_handle = coordinator.hass.loop.call_later(
        99, lambda: None
    )

    with patch.object(coordinator, "_do_discovery", AsyncMock()) as do_discovery:
        await coordinator._discover_unknown_devices()

    do_discovery.assert_awaited_once()
    assert coordinator._unknown_device_discovery_handle is None


async def test_discover_unknown_devices_failure_clears_handle(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A failed re-discovery still clears the handle, so a later event can retry."""
    coordinator._unknown_device_discovery_handle = coordinator.hass.loop.call_later(
        99, lambda: None
    )

    with patch.object(
        coordinator, "_do_discovery", AsyncMock(side_effect=RuntimeError("boom"))
    ):
        await coordinator._discover_unknown_devices()

    assert coordinator._unknown_device_discovery_handle is None


async def test_async_disconnect_cancels_pending_rediscovery(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Disconnecting cancels a re-discovery run still in flight."""
    coordinator._unknown_device_discovery_handle = coordinator.hass.loop.call_later(
        99, lambda: None
    )

    async def _hang() -> None:
        # Stands in for a gateway round trip that never returns; the test
        # only cares that async_disconnect cancels it, not that it finishes.
        await asyncio.sleep(3600)

    with patch.object(coordinator, "_do_discovery", side_effect=_hang):
        coordinator._unknown_device_discovery_task = coordinator.hass.async_create_task(
            coordinator._discover_unknown_devices()
        )
        await asyncio.sleep(0)  # let the task start and reach the sleep

        await coordinator.async_disconnect()

    assert coordinator._unknown_device_discovery_handle is None
    assert coordinator._unknown_device_discovery_task is None


async def test_exclude_already_absent_device_succeeds(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Excluding a device already gone from the map counts as success.

    A delete event or a fresh discovery can remove it first (e.g. it was
    excluded through the official app); there is nothing left to reject,
    so this must not report a failure that creates a misleading repair
    issue.
    """
    assert await coordinator.async_exclude_device("dev-1") is True


async def test_msg_consumer_resolves_pending_reply_on_error_message(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A gateway ErrorMessage resolves the matching pending future.

    Only Reply used to be matched against _pending_replies; an
    ErrorMessage fell through to the generic event handler, which
    silently drops it, so a rejected command just timed out instead of
    surfacing the actual rejection.
    """
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    coordinator._pending_replies["req-1"] = fut

    error = ErrorMessage(
        metadata=ErrorMetadata(error_source="test"),
        request_id="req-1",
        success=False,
        payload={"vs": "not allowed"},
    )
    coordinator._msg_queue.put_nowait(IngressMessageList([error]).model_dump_json())

    task = loop.create_task(coordinator._msg_consumer())
    try:
        result = await asyncio.wait_for(fut, timeout=1)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    assert result == error
    assert "req-1" not in coordinator._pending_replies


async def test_socket_teardown_drops_queued_frames(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Frames queued for a closed socket are not replayed on the next connection."""
    coordinator._msg_queue.put_nowait('[{"op": "update"}]')
    session = MagicMock()
    session.ws_connect.side_effect = aiohttp.ClientConnectionError("gone")

    with patch(
        "homeassistant.components.gardena_smart_local.coordinator.async_get_clientsession",
        return_value=session,
    ):
        task = asyncio.get_running_loop().create_task(coordinator._ws_loop())
        # Let the loop fail its connect and run its teardown.
        for _ in range(10):
            await asyncio.sleep(0)
        assert session.ws_connect.called
        assert coordinator._msg_queue.empty()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
