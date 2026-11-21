"""HTTP snapshots remain authoritative across concurrent WebSocket notifications."""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock, patch

from aiolanbon import LanbonConnectionError
from aiolanbon.models import DeviceSnapshot, Event, SnapshotRefresh
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import GATEWAY_ID, gateway_info, snapshot

from tests.common import MockConfigEntry, async_fire_time_changed


def two_switch_snapshot(revision: str = "1", on: bool = False) -> DeviceSnapshot:
    """Return two switches with the same authoritative on/off state."""
    current = snapshot()
    device = current.devices[0]
    first = replace(device.components[0], state={"on": on})
    second = replace(first, id="switch:2", name="Second")
    return replace(
        current,
        revision=revision,
        devices=(replace(device, components=(first, second)),),
    )


def notification(kind: str = "state_changed", revision: str = "2") -> Event:
    """Build an event whose on/off and online fields must not override HTTP."""
    return Event.from_dict(
        {
            "protocol_version": "1.0.0",
            "event_id": "notification-" + revision,
            "revision": revision,
            "type": kind,
            "device_id": GATEWAY_ID,
            "component_id": "switch:1",
            "state": {"on": True},
            "online": False,
        }
    )


@pytest.fixture
async def websocket_notifications(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> AsyncGenerator[
    tuple[MockConfigEntry, asyncio.Queue[Event | SnapshotRefresh], asyncio.Queue[None]]
]:
    """Load a real integration with a controllable notification stream."""
    queue: asyncio.Queue[Event | SnapshotRefresh] = asyncio.Queue()
    processed: asyncio.Queue[None] = asyncio.Queue()
    closed = asyncio.Event()

    async def events() -> AsyncGenerator[Event | SnapshotRefresh]:
        try:
            yield SnapshotRefresh(reason=SnapshotRefresh.CONNECTED)
            while True:
                yield await queue.get()
                processed.put_nowait(None)
        finally:
            closed.set()

    stream = events()
    mock_lanbon_client.get_devices.return_value = two_switch_snapshot()
    with (
        patch(
            "homeassistant.components.lanbon.LanbonClient.get_info",
            return_value=gateway_info(transports={"http": True, "events": "websocket"}),
        ),
        patch(
            "homeassistant.components.lanbon.LanbonClient.listen", return_value=stream
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_config_entry, queue, processed
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await stream.aclose()
        assert closed.is_set()


@pytest.mark.parametrize(
    "kind",
    ["state_changed", "availability_changed", "topology_changed", "future_event"],
)
async def test_notifications_refresh_the_complete_snapshot(
    hass: HomeAssistant,
    websocket_notifications: tuple[
        MockConfigEntry, asyncio.Queue[Event | SnapshotRefresh], asyncio.Queue[None]
    ],
    mock_lanbon_client: MagicMock,
    kind: str,
) -> None:
    """Notification fields never overwrite HTTP state or hide sibling updates."""
    entry, queue, processed = websocket_notifications
    current = two_switch_snapshot("fresh")
    device = current.devices[0]
    second = replace(device.components[1], state={"on": True})
    authoritative = replace(
        current, devices=(replace(device, components=(device.components[0], second)),)
    )
    mock_lanbon_client.get_devices.return_value = authoritative
    mock_lanbon_client.get_devices.reset_mock()
    queue.put_nowait(notification(kind))
    await processed.get()
    await hass.async_block_till_done()
    first_id, second_id = hass.states.async_entity_ids("switch")
    assert hass.states.get(first_id).state == STATE_OFF
    assert hass.states.get(second_id).state == STATE_ON
    assert entry.runtime_data.data == authoritative
    mock_lanbon_client.get_devices.assert_awaited_once_with(if_none_match=None)


@pytest.mark.parametrize("event_revision", ["older", "46", "fresh"])
async def test_delayed_event_after_snapshot_cannot_roll_state_back(
    hass: HomeAssistant,
    websocket_notifications: tuple[
        MockConfigEntry, asyncio.Queue[Event | SnapshotRefresh], asyncio.Queue[None]
    ],
    mock_lanbon_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    event_revision: str,
) -> None:
    """Old, opaque and duplicate notifications all refetch the authoritative state."""
    entry, queue, processed = websocket_notifications
    authoritative = two_switch_snapshot("fresh")
    mock_lanbon_client.get_devices.return_value = authoritative
    freezer.tick(timedelta(seconds=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    queue.put_nowait(notification(revision=event_revision))
    await processed.get()
    await hass.async_block_till_done()
    assert {state.state for state in hass.states.async_all("switch")} == {STATE_OFF}
    assert entry.runtime_data.data == authoritative


async def test_repeated_notifications_keep_all_switches_current(
    hass: HomeAssistant,
    websocket_notifications: tuple[
        MockConfigEntry, asyncio.Queue[Event | SnapshotRefresh], asyncio.Queue[None]
    ],
    mock_lanbon_client: MagicMock,
) -> None:
    """Repeated notifications always recover the sibling state through full GETs."""
    entry, queue, processed = websocket_notifications
    authoritative = two_switch_snapshot("complete", on=True)
    mock_lanbon_client.get_devices.return_value = authoritative
    mock_lanbon_client.get_devices.reset_mock()
    for revision in ("4", "2", "opaque", "1", "4"):
        queue.put_nowait(notification(revision=revision))
        await processed.get()
        assert {state.state for state in hass.states.async_all("switch")} == {STATE_ON}
        assert entry.runtime_data.data == authoritative
    assert mock_lanbon_client.get_devices.await_count == 5
    assert all(
        call.kwargs == {"if_none_match": None}
        for call in mock_lanbon_client.get_devices.await_args_list
    )


async def test_failed_notification_refresh_recovers_through_polling(
    hass: HomeAssistant,
    websocket_notifications: tuple[
        MockConfigEntry, asyncio.Queue[Event | SnapshotRefresh], asyncio.Queue[None]
    ],
    mock_lanbon_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed GET cannot publish event state; polling recovers without replay."""
    entry, queue, _processed = websocket_notifications
    failed = asyncio.Event()

    async def fail(*, if_none_match: str | None) -> DeviceSnapshot:
        failed.set()
        raise LanbonConnectionError("offline")

    mock_lanbon_client.get_devices.side_effect = fail
    queue.put_nowait(notification())
    await failed.wait()
    await hass.async_block_till_done()
    assert {state.state for state in hass.states.async_all("switch")} == {
        STATE_UNAVAILABLE
    }
    assert not entry.runtime_data.last_update_success
    mock_lanbon_client.get_devices.side_effect = None
    mock_lanbon_client.get_devices.return_value = two_switch_snapshot("recovered")
    freezer.tick(timedelta(seconds=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert {state.state for state in hass.states.async_all("switch")} == {STATE_OFF}
    assert entry.runtime_data.last_update_success


@pytest.mark.parametrize("remove_device", [False, True])
async def test_topology_notifications_remove_and_restore_availability(
    hass: HomeAssistant,
    websocket_notifications: tuple[
        MockConfigEntry, asyncio.Queue[Event | SnapshotRefresh], asyncio.Queue[None]
    ],
    mock_lanbon_client: MagicMock,
    remove_device: bool,
) -> None:
    """An old event cannot resurrect a component absent from the HTTP snapshot."""
    entry, queue, processed = websocket_notifications
    current = two_switch_snapshot()
    device = current.devices[0]
    remaining = () if remove_device else (replace(device, components=()),)
    mock_lanbon_client.get_devices.return_value = replace(current, devices=remaining)
    queue.put_nowait(notification("topology_changed"))
    await processed.get()
    assert {state.state for state in hass.states.async_all("switch")} == {
        STATE_UNAVAILABLE
    }
    restored = two_switch_snapshot("restored", on=True)
    mock_lanbon_client.get_devices.return_value = restored
    queue.put_nowait(notification())
    await processed.get()
    assert {state.state for state in hass.states.async_all("switch")} == {STATE_ON}
    assert entry.runtime_data.data == restored


async def test_reboot_can_replace_an_opaque_revision(
    hass: HomeAssistant,
    websocket_notifications: tuple[
        MockConfigEntry, asyncio.Queue[Event | SnapshotRefresh], asyncio.Queue[None]
    ],
    mock_lanbon_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Revision values are not sorted numerically or lexically across reboots."""
    entry, queue, processed = websocket_notifications
    mock_lanbon_client.get_devices.return_value = two_switch_snapshot("46", on=True)
    queue.put_nowait(notification())
    await processed.get()
    assert {state.state for state in hass.states.async_all("switch")} == {STATE_ON}
    mock_lanbon_client.get_devices.return_value = two_switch_snapshot("1")
    freezer.tick(timedelta(seconds=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert {state.state for state in hass.states.async_all("switch")} == {STATE_OFF}
    assert entry.runtime_data.data.revision == "1"


@pytest.mark.parametrize(
    ("event_revision", "snapshot_revision"),
    [("2", "3"), ("old-opaque", "new-opaque")],
)
async def test_stale_websocket_event_during_http_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lanbon_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    event_revision: str,
    snapshot_revision: str,
) -> None:
    """An older on event cannot overwrite the newer authoritative off snapshot."""
    emit = asyncio.Event()
    yielded = asyncio.Event()
    delivered = asyncio.Event()
    hold = asyncio.Event()
    entered = asyncio.Event()
    release = asyncio.Event()
    authoritative = replace(snapshot(), revision=snapshot_revision)

    async def events() -> AsyncGenerator[SnapshotRefresh | Event]:
        yield SnapshotRefresh(reason=SnapshotRefresh.CONNECTED)
        await emit.wait()
        yielded.set()
        yield Event.from_dict(
            {
                "protocol_version": "1.0.0",
                "event_id": "delayed-event",
                "revision": event_revision,
                "type": "state_changed",
                "device_id": GATEWAY_ID,
                "component_id": "switch:1",
                "state": {"on": True},
            }
        )
        delivered.set()
        await hold.wait()

    async def response(*, if_none_match: str | None) -> DeviceSnapshot:
        entered.set()
        await release.wait()
        return authoritative

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
        await hass.async_block_till_done()
        entity_id = hass.states.async_entity_ids("switch")[0]
        mock_lanbon_client.get_devices.side_effect = response
        freezer.tick(timedelta(seconds=16))
        async_fire_time_changed(hass)
        await entered.wait()
        emit.set()
        await yielded.wait()
        await hass.async_block_till_done()
        release.set()
        await delivered.wait()
        await hass.async_block_till_done()
        actual_state = hass.states.get(entity_id).state
        actual_revision = mock_config_entry.runtime_data.data.revision
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert actual_state == STATE_OFF
        assert actual_revision == snapshot_revision
        mock_lanbon_client.get_devices.assert_awaited_with(if_none_match=None)
