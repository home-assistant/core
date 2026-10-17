"""Test setup cancellation and controller cleanup."""

import asyncio
from unittest.mock import MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from terrestream_local.models import Snapshot

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    "target",
    [
        pytest.param(
            "homeassistant.components.terrestream_local.Client.return_value.refresh",
            id="first-refresh",
        ),
        pytest.param(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            id="platform-setup",
        ),
    ],
)
async def test_setup_cancellation_releases_lease(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    target: str,
) -> None:
    """Release ownership without swallowing cancellation during setup."""
    started = asyncio.Event()

    async def block_setup(*args: object) -> None:
        started.set()
        await asyncio.Future()

    with patch(target, side_effect=block_setup):
        task = hass.async_create_task(
            hass.config_entries.async_setup(config_entry.entry_id)
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert task.cancelled()
    mock_client.command.assert_any_await("release")
    assert mock_client.command.await_args == call("release")
    assert not hass.states.async_all("sensor")


async def test_unload_waits_for_in_flight_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Finish polling and clock synchronization before releasing the lease."""
    freezer.move_to("2026-01-01T00:00:00.500000+00:00")
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.command.reset_mock()
    refresh_started = asyncio.Event()
    finish_refresh = asyncio.Event()
    shutdown_started = asyncio.Event()
    snapshot: Snapshot = mock_client.refresh.return_value

    async def blocked_refresh() -> Snapshot:
        refresh_started.set()
        await finish_refresh.wait()
        return snapshot

    coordinator = config_entry.runtime_data
    shutdown = coordinator.async_shutdown

    async def track_shutdown() -> None:
        await shutdown()
        shutdown_started.set()

    mock_client.refresh.side_effect = blocked_refresh
    freezer.tick(60)
    async_fire_time_changed(hass)
    await refresh_started.wait()

    with patch.object(coordinator, "async_shutdown", side_effect=track_shutdown):
        unload_task = hass.async_create_task(
            hass.config_entries.async_unload(config_entry.entry_id)
        )
        await shutdown_started.wait()
        try:
            mock_client.command.assert_not_awaited()
        finally:
            finish_refresh.set()
            assert await unload_task
            await hass.async_block_till_done()

    assert mock_client.command.await_args_list == [
        call("time", epoch=1767225660, uncertainty_ms=1000),
        call("release"),
    ]
