"""Tests for snapshot recovery and concurrent WebSocket updates."""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock, patch

from aiolanbon import (
    LanbonConnectionError,
    LanbonEventsUnsupportedError,
    SnapshotRefresh,
)
from aiolanbon.models import DeviceSnapshot, Event, GatewayInfo
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.lanbon.coordinator import LanbonCoordinator
from homeassistant.components.lanbon.switch import LanbonSwitch
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import GATEWAY_ID, gateway_info, snapshot

from tests.common import MockConfigEntry, async_fire_time_changed


def state_event(revision: str) -> Event:
    """Return an event turning on the switch."""
    return Event.from_dict(
        {
            "protocol_version": "1.0.0",
            "event_id": "test-event",
            "revision": revision,
            "type": "state_changed",
            "device_id": GATEWAY_ID,
            "component_id": "switch:1",
            "state": {"on": True},
        }
    )


@pytest.mark.parametrize("etag", ["46", None])
async def test_reboot_snapshot(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
    etag: str | None,
) -> None:
    """A full response after reboot must replace state from the previous boot."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data
    coordinator._apply_event(state_event("46"))
    coordinator._etag = etag
    mock_lanbon_client.get_devices.return_value = snapshot()
    mock_lanbon_client.get_devices.reset_mock()
    result = await coordinator._async_update_data()
    assert result.revision == "1"
    assert result.devices[0].components[0].state["on"] is False
    assert coordinator._etag == "1"
    mock_lanbon_client.get_devices.assert_awaited_once_with(if_none_match=etag)


@pytest.mark.parametrize("revision", ["2", "opaque-etag"])
async def test_event_during_snapshot(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
    revision: str,
) -> None:
    """A response cannot overwrite an event received while it was in flight."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data

    async def get_devices(*, if_none_match: str | None) -> DeviceSnapshot:
        coordinator._apply_event(state_event(revision))
        return snapshot()

    mock_lanbon_client.get_devices.side_effect = get_devices
    result = await coordinator._async_update_data()
    assert result.revision == revision
    assert result.devices[0].components[0].state["on"] is True
    assert coordinator._etag is None


async def test_not_modified_preserves_event(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> None:
    """A conditional response must preserve the latest in-memory event."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data

    async def get_devices(*, if_none_match: str | None) -> None:
        coordinator._apply_event(state_event("2"))

    mock_lanbon_client.get_devices.side_effect = get_devices
    result = await coordinator._async_update_data()
    assert result.revision == "2"
    assert result.devices[0].components[0].state["on"] is True


async def test_websocket_refresh_order_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> None:
    """Startup refresh precedes later events and unload closes the listener."""
    delivered = asyncio.Event()
    closed = asyncio.Event()
    hold_open = asyncio.Event()

    async def events() -> AsyncGenerator[SnapshotRefresh | Event]:
        try:
            yield SnapshotRefresh(reason=SnapshotRefresh.CONNECTED)
            yield state_event("2")
            delivered.set()
            await hold_open.wait()
        finally:
            closed.set()

    with (
        patch(
            "homeassistant.components.lanbon.LanbonClient.get_info",
            return_value=gateway_info(transports={"http": True, "events": "websocket"}),
        ),
        patch(
            "homeassistant.components.lanbon.LanbonClient.listen", return_value=events()
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await delivered.wait()
        await hass.async_block_till_done()
        coordinator = mock_config_entry.runtime_data
        assert mock_lanbon_client.get_devices.await_count == 2
        assert coordinator.data.revision == "2"
        assert coordinator.data.devices[0].components[0].state["on"] is True
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await closed.wait()
        await hass.async_block_till_done()
        assert coordinator._events_task.cancelled()


@pytest.mark.parametrize(
    "error",
    [LanbonEventsUnsupportedError("unsupported"), LanbonConnectionError("lost")],
)
async def test_websocket_failure_keeps_polling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lanbon_client: MagicMock,
    error: Exception,
) -> None:
    """Losing push support leaves polling and the existing snapshot available."""

    async def events() -> AsyncGenerator[Event]:
        yield state_event("2")
        raise error

    with (
        patch(
            "homeassistant.components.lanbon.LanbonClient.get_info",
            return_value=gateway_info(transports={"http": True, "events": "websocket"}),
        ),
        patch(
            "homeassistant.components.lanbon.LanbonClient.listen", return_value=events()
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        coordinator = mock_config_entry.runtime_data
        await coordinator._events_task
        await hass.async_block_till_done()
        assert coordinator._use_ws is False
        assert coordinator.update_interval.total_seconds() == 15
        mock_lanbon_client.get_devices.reset_mock()
        await coordinator.async_refresh()
        mock_lanbon_client.get_devices.assert_awaited_once()
        assert coordinator.last_update_success


async def test_concurrent_event_requires_complete_snapshot(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> None:
    """An event for A must not hide a missed update for B behind a new ETag."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data
    initial = snapshot()
    device = initial.devices[0]
    first = device.components[0]
    second = replace(first, id="switch:2")
    initial = replace(initial, devices=(replace(device, components=(first, second)),))
    complete = replace(
        initial,
        revision="3",
        devices=(
            replace(
                device,
                components=(
                    replace(first, state={"on": True}),
                    replace(second, state={"on": True}),
                ),
            ),
        ),
    )
    coordinator.async_set_updated_data(initial)

    async def concurrent_response(*, if_none_match: str | None) -> DeviceSnapshot:
        coordinator._apply_event(state_event("3"))
        return complete

    mock_lanbon_client.get_devices.side_effect = concurrent_response
    await coordinator.async_refresh()
    assert coordinator.data.devices[0].components[0].state["on"] is True
    assert coordinator.data.devices[0].components[1].state["on"] is True
    mock_lanbon_client.get_devices.reset_mock()
    mock_lanbon_client.get_devices.side_effect = None
    mock_lanbon_client.get_devices.return_value = complete
    await coordinator.async_refresh()
    mock_lanbon_client.get_devices.assert_awaited_once_with(if_none_match=None)
    assert coordinator.data.devices[0].components[1].state["on"] is True
    mock_lanbon_client.get_devices.return_value = None
    await coordinator.async_refresh()
    assert coordinator.data.devices[0].components[1].state["on"] is True


async def test_reconnect_waits_for_actual_snapshot(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> None:
    """Reconnection cannot consume events before a forced refresh completes."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data
    await coordinator.async_request_refresh()
    delivered = asyncio.Event()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def response(*, if_none_match: str | None) -> DeviceSnapshot:
        entered.set()
        await release.wait()
        return snapshot()

    async def events() -> AsyncGenerator[SnapshotRefresh | Event]:
        yield SnapshotRefresh(reason=SnapshotRefresh.RECONNECTED)
        delivered.set()
        yield state_event("2")

    mock_lanbon_client.get_devices.side_effect = response
    with patch.object(coordinator.client, "listen", return_value=events()):
        listener = setup_integration.async_create_background_task(
            hass, coordinator._events_loop(), "lanbon-test-reconnect"
        )
        await hass.async_block_till_done()
        assert entered.is_set()
        assert not delivered.is_set()
        release.set()
        await listener
    assert delivered.is_set()
    assert mock_lanbon_client.get_devices.call_args.kwargs["if_none_match"] is None
    assert coordinator.data.devices[0].components[0].state["on"] is True


async def test_reconnect_waits_for_inflight_poll(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> None:
    """A poll completing after reconnect must not restore a conditional ETag."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data
    entered = asyncio.Event()
    release = asyncio.Event()
    delivered = asyncio.Event()

    async def response(*, if_none_match: str | None) -> DeviceSnapshot:
        entered.set()
        await release.wait()
        return snapshot()

    async def events() -> AsyncGenerator[SnapshotRefresh | Event]:
        yield SnapshotRefresh(reason=SnapshotRefresh.RECONNECTED)
        delivered.set()
        yield state_event("2")

    mock_lanbon_client.get_devices.side_effect = response
    poll = setup_integration.async_create_background_task(
        hass, coordinator.async_refresh(), "lanbon-test-poll"
    )
    await entered.wait()
    with patch.object(coordinator.client, "listen", return_value=events()):
        listener = setup_integration.async_create_background_task(
            hass, coordinator._events_loop(), "lanbon-test-reconnect"
        )
        await hass.async_block_till_done()
        assert not delivered.is_set()
        release.set()
        await poll
        await listener
    assert mock_lanbon_client.get_devices.await_count == 3
    assert mock_lanbon_client.get_devices.call_args.kwargs["if_none_match"] is None
    assert delivered.is_set()


async def test_failed_reconnect_snapshot_stops_event_updates(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> None:
    """A partial event must not mark a failed full resync healthy."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data
    delivered = asyncio.Event()

    async def events() -> AsyncGenerator[SnapshotRefresh | Event]:
        yield SnapshotRefresh(reason=SnapshotRefresh.RECONNECTED)
        delivered.set()
        yield state_event("2")

    mock_lanbon_client.get_devices.side_effect = LanbonConnectionError("offline")
    with patch.object(coordinator.client, "listen", return_value=events()):
        await coordinator._events_loop()
    assert not delivered.is_set()
    assert not coordinator.last_update_success
    assert not coordinator._use_ws
    mock_lanbon_client.get_devices.side_effect = None
    await coordinator.async_refresh()
    assert coordinator.last_update_success


async def test_unload_cancels_pending_snapshot(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> None:
    """Unloading during a forced GET leaves no independent refresh task."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data
    entered = asyncio.Event()
    cancelled = asyncio.Event()
    hold = asyncio.Event()

    async def response(*, if_none_match: str | None) -> DeviceSnapshot:
        entered.set()
        try:
            await hold.wait()
        finally:
            cancelled.set()
        return snapshot()

    async def events() -> AsyncGenerator[SnapshotRefresh]:
        yield SnapshotRefresh(reason=SnapshotRefresh.RECONNECTED)

    mock_lanbon_client.get_devices.side_effect = response
    with patch.object(coordinator.client, "listen", return_value=events()):
        coordinator._events_task = setup_integration.async_create_background_task(
            hass, coordinator._events_loop(), "lanbon-test-unload"
        )
        await entered.wait()
        assert await hass.config_entries.async_unload(setup_integration.entry_id)
        await hass.async_block_till_done()
    assert cancelled.is_set()
    assert coordinator._events_task.cancelled()


@pytest.mark.parametrize(
    "event",
    [
        state_event("4"),
        replace(state_event("4"), type="availability_changed", online=True),
    ],
    ids=["state", "availability"],
)
async def test_events_do_not_postpone_snapshot_recovery(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    event: Event,
) -> None:
    """Frequent partial events cannot starve automatic recovery of another switch."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data
    initial = snapshot()
    device = initial.devices[0]
    first = device.components[0]
    second = replace(first, id="switch:2")
    initial = replace(initial, devices=(replace(device, components=(first, second)),))
    complete = replace(
        initial,
        revision="3",
        devices=(
            replace(
                device,
                components=(
                    replace(first, state={"on": True}),
                    replace(second, state={"on": True}),
                ),
            ),
        ),
    )
    coordinator.async_set_updated_data(initial)

    mock_lanbon_client.get_devices.return_value = complete
    mock_lanbon_client.get_devices.reset_mock()

    # Only advance Core's timers from here: do not manually request recovery.
    for _ in range(6):
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert coordinator._apply_event(event)

    assert 2 <= mock_lanbon_client.get_devices.await_count <= 4
    assert coordinator.data.devices[0].components[1].state["on"] is True
    assert all(
        call.kwargs["if_none_match"] is None
        for call in mock_lanbon_client.get_devices.await_args_list
    )
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    mock_lanbon_client.get_devices.reset_mock()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_lanbon_client.get_devices.assert_not_awaited()


async def test_partial_event_preserves_poll_failure_until_recovery(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A partial event cannot heal a failed snapshot or postpone its retry."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data
    mock_lanbon_client.get_devices.side_effect = LanbonConnectionError("offline")
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator._apply_event(state_event("2"))
    assert not coordinator.last_update_success
    mock_lanbon_client.get_devices.side_effect = None
    mock_lanbon_client.get_devices.reset_mock()
    for _ in range(2):
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        coordinator._apply_event(state_event("3"))
    mock_lanbon_client.get_devices.assert_awaited_once_with(if_none_match=None)
    assert coordinator.last_update_success


@pytest.mark.parametrize("revision", ["1", "46", "opaque-etag"])
@pytest.mark.parametrize(
    "event",
    [
        state_event("2"),
        replace(state_event("2"), type="availability_changed", online=False),
    ],
    ids=["state", "availability"],
)
async def test_repeated_overlap_recovers_sibling(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    revision: str,
    event: Event,
) -> None:
    """Every scheduled GET can overlap an event without starving other fields."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data
    initial = snapshot()
    device = initial.devices[0]
    first = device.components[0]
    second = replace(first, id="switch:2")
    initial = replace(initial, devices=(replace(device, components=(first, second)),))
    coordinator.async_set_updated_data(initial)
    complete = replace(
        initial,
        revision=revision,
        devices=(
            replace(device, components=(first, replace(second, state={"on": True}))),
        ),
    )

    async def response(*, if_none_match: str | None) -> DeviceSnapshot:
        assert coordinator._apply_event(event)
        await asyncio.sleep(0)
        return complete

    mock_lanbon_client.get_devices.side_effect = response
    mock_lanbon_client.get_devices.reset_mock()
    for _ in range(5):
        freezer.tick(timedelta(seconds=20))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert coordinator.data.devices[0].components[1].state["on"] is True
        assert coordinator.data.devices[0].components[0].state["on"] == (
            event.type == "state_changed"
        )
        assert coordinator.data.devices[0].online == (event.type == "state_changed")
        assert coordinator._etag is None
    assert mock_lanbon_client.get_devices.await_count == 5
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_lanbon_client.get_devices.await_count == 5


@pytest.mark.parametrize("remove_device", [False, True])
async def test_overlap_preserves_snapshot_topology(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
    remove_device: bool,
) -> None:
    """Events cannot resurrect removed components/devices or hide new ones."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data
    initial = snapshot()
    device = initial.devices[0]
    added = replace(device.components[0], id="switch:new", state={"on": True})
    updated = replace(
        device, id="new-device" if remove_device else device.id, components=(added,)
    )
    complete = replace(initial, devices=(updated,))

    async def response(*, if_none_match: str | None) -> DeviceSnapshot:
        assert coordinator._apply_event(state_event("2"))
        return complete

    mock_lanbon_client.get_devices.side_effect = response
    await coordinator.async_refresh()
    assert coordinator.data.devices == (updated,)
    assert coordinator._etag is None


@pytest.mark.parametrize(
    "error", [LanbonConnectionError("offline"), asyncio.CancelledError()]
)
async def test_failed_overlap_does_not_replay_old_events(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
    error: BaseException,
) -> None:
    """A failed/cancelled GET must not leak its events into a later snapshot."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data

    async def response(*, if_none_match: str | None) -> DeviceSnapshot:
        coordinator._apply_event(state_event("46"))
        raise error

    mock_lanbon_client.get_devices.side_effect = response
    with pytest.raises((Exception, asyncio.CancelledError)):
        await coordinator._async_update_data()
    mock_lanbon_client.get_devices.side_effect = None
    mock_lanbon_client.get_devices.return_value = snapshot()
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data.devices[0].components[0].state["on"] is False
    assert coordinator._etag == "1"


async def test_overlap_keeps_latest_state_and_availability(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> None:
    """Multiple events preserve the last value of each independent field."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data

    async def response(*, if_none_match: str | None) -> DeviceSnapshot:
        coordinator._apply_event(state_event("2"))
        coordinator._apply_event(
            replace(state_event("3"), type="availability_changed", online=False)
        )
        coordinator._apply_event(replace(state_event("4"), state={"on": False}))
        coordinator._apply_event(state_event("5"))
        return snapshot()

    mock_lanbon_client.get_devices.side_effect = response
    await coordinator.async_refresh()
    assert coordinator.data.devices[0].components[0].state["on"] is True
    assert coordinator.data.devices[0].online is False
    assert coordinator.data.revision == "5"
    assert coordinator._etag is None


@pytest.mark.parametrize(
    ("info", "devices", "device_requests"),
    [
        (
            gateway_info(
                gateway_id="other-gateway",
                transports={"http": True, "events": "websocket"},
            ),
            snapshot(),
            0,
        ),
        (
            gateway_info(transports={"http": True, "events": "websocket"}),
            replace(snapshot(), gateway_id="other-gateway"),
            1,
        ),
    ],
    ids=["info", "snapshot"],
)
async def test_setup_rejects_wrong_gateway(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lanbon_client: MagicMock,
    info: GatewayInfo,
    devices: DeviceSnapshot,
    device_requests: int,
) -> None:
    """An address reassigned to another gateway cannot create entities or listen."""
    mock_lanbon_client.get_devices.return_value = devices
    with (
        patch(
            "homeassistant.components.lanbon.LanbonClient.get_info", return_value=info
        ),
        patch("homeassistant.components.lanbon.LanbonClient.listen") as listen,
    ):
        mock_config_entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.states.async_all("switch")
    listen.assert_not_called()
    mock_lanbon_client.send_command.assert_not_awaited()
    assert mock_lanbon_client.get_devices.await_count == device_requests


async def test_foreign_snapshot_blocks_control_and_recovers(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> None:
    """Reject foreign data, disable control/events, then recover on the real gateway."""
    coordinator = setup_integration.runtime_data
    original = coordinator.data
    entity = LanbonSwitch(coordinator, GATEWAY_ID, "switch:1")
    mock_lanbon_client.get_devices.return_value = replace(
        snapshot(), gateway_id="other-gateway", revision="foreign"
    )
    await coordinator.async_refresh()
    assert coordinator.data is original
    assert not coordinator.last_update_success
    assert not coordinator.gateway_verified
    assert coordinator._etag is None
    assert not entity.available
    assert not coordinator._apply_event(state_event("99"))
    with pytest.raises(HomeAssistantError, match="identity"):
        await entity.async_turn_on()
    mock_lanbon_client.send_command.assert_not_awaited()

    mock_lanbon_client.get_devices.return_value = snapshot()
    with patch(
        "homeassistant.components.lanbon.LanbonClient.get_info",
        return_value=gateway_info(),
    ) as get_info:
        await coordinator.async_refresh()
    get_info.assert_awaited_once()
    mock_lanbon_client.get_devices.assert_awaited_with(if_none_match=None)
    assert coordinator.last_update_success
    assert coordinator.gateway_verified
    assert entity.available
    await entity.async_turn_on()
    mock_lanbon_client.send_command.assert_awaited_once_with(
        GATEWAY_ID, "switch:1", "set_on", {"on": True}
    )


async def test_partial_recovery_does_not_restore_control(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> None:
    """A matching info response alone cannot validate the retained old snapshot."""
    coordinator = setup_integration.runtime_data
    mock_lanbon_client.get_devices.return_value = replace(
        snapshot(), gateway_id="foreign"
    )
    await coordinator.async_refresh()
    mock_lanbon_client.get_devices.return_value = None
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert not coordinator.gateway_verified
    assert not coordinator._apply_event(state_event("99"))
    mock_lanbon_client.send_command.assert_not_awaited()
