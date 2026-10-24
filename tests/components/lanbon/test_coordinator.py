"""Tests for authoritative refresh, reconnect, gateway validation and unloading."""

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


async def test_websocket_refresh_order_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> None:
    """Startup refresh precedes later events and unload closes the listener."""
    current = snapshot()
    device = current.devices[0]
    component = replace(device.components[0], state={"on": True})
    changed = replace(
        current, revision="2", devices=(replace(device, components=(component,)),)
    )
    mock_lanbon_client.get_devices.side_effect = [current, current, changed]
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
        assert mock_lanbon_client.get_devices.await_count == 3
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
    freezer: FrozenDateTimeFactory,
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
        freezer.tick(timedelta(seconds=16))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        mock_lanbon_client.get_devices.assert_awaited_once()
        assert coordinator.last_update_success


async def test_reconnect_waits_for_actual_snapshot(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> None:
    """Reconnection cannot consume events before a forced refresh completes."""
    coordinator: LanbonCoordinator = setup_integration.runtime_data
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": hass.states.async_entity_ids("switch")[0]},
        blocking=True,
    )
    delivered = asyncio.Event()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def response(*, if_none_match: str | None) -> DeviceSnapshot:
        entered.set()
        await release.wait()
        current = snapshot()
        device = current.devices[0]
        return replace(
            current,
            revision="2",
            devices=(
                replace(
                    device,
                    components=(replace(device.components[0], state={"on": True}),),
                ),
            ),
        )

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
    freezer: FrozenDateTimeFactory,
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
    freezer.tick(timedelta(seconds=16))
    async_fire_time_changed(hass)
    await entered.wait()
    with patch.object(coordinator.client, "listen", return_value=events()):
        listener = setup_integration.async_create_background_task(
            hass, coordinator._events_loop(), "lanbon-test-reconnect"
        )
        await hass.async_block_till_done()
        assert not delivered.is_set()
        release.set()
        await hass.async_block_till_done()
        await listener
    assert mock_lanbon_client.get_devices.await_count == 4
    assert mock_lanbon_client.get_devices.call_args.kwargs["if_none_match"] is None
    assert delivered.is_set()


async def test_failed_reconnect_snapshot_stops_event_updates(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: MagicMock,
    freezer: FrozenDateTimeFactory,
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
    freezer.tick(timedelta(seconds=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
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
    freezer: FrozenDateTimeFactory,
) -> None:
    """Reject foreign data, disable control/events, then recover on the real gateway."""
    coordinator = setup_integration.runtime_data
    original = coordinator.data
    entity = LanbonSwitch(coordinator, GATEWAY_ID, "switch:1")
    mock_lanbon_client.get_devices.return_value = replace(
        snapshot(), gateway_id="other-gateway", revision="foreign"
    )
    freezer.tick(timedelta(seconds=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.data is original
    assert not coordinator.last_update_success
    assert not coordinator.gateway_verified
    assert coordinator._etag is None
    assert not entity.available
    with pytest.raises(HomeAssistantError, match="identity"):
        await entity.async_turn_on()
    mock_lanbon_client.send_command.assert_not_awaited()

    mock_lanbon_client.get_devices.return_value = snapshot()
    with patch(
        "homeassistant.components.lanbon.LanbonClient.get_info",
        return_value=gateway_info(),
    ) as get_info:
        freezer.tick(timedelta(seconds=16))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
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
    freezer: FrozenDateTimeFactory,
) -> None:
    """A matching info response alone cannot validate the retained old snapshot."""
    coordinator = setup_integration.runtime_data
    mock_lanbon_client.get_devices.return_value = replace(
        snapshot(), gateway_id="foreign"
    )
    freezer.tick(timedelta(seconds=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_lanbon_client.get_devices.return_value = None
    freezer.tick(timedelta(seconds=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert not coordinator.gateway_verified
    mock_lanbon_client.send_command.assert_not_awaited()
