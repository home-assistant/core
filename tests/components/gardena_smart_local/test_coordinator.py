"""Tests for the GARDENA smart local coordinator."""

from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from gardena_smart_local_api.devices.irrigation import Gen2WaterControl
from gardena_smart_local_api.messages import (
    ErrorMessage,
    ErrorMetadata,
    Event,
    IngressMessageList,
    Reply,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gardena_smart_local.const import (
    CONF_FINGERPRINT,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.components.gardena_smart_local.coordinator import (
    GardenaSmartLocalCoordinator,
    IncludableDeviceInfo,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

MOCK_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_PASSWORD: "testpassword",
    CONF_FINGERPRINT: "ab" * 32,
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
        MOCK_DATA[CONF_FINGERPRINT],
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
    """A gateway ErrorMessage resolves the pending request instead of timing out."""
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


def _excludable_device() -> MagicMock:
    device = MagicMock()
    device.id = "dev-1"
    device.build_exclusion_obj.return_value = "EXCLUDE_OBJ"
    return device


async def test_exclude_success_drops_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A confirmed exclusion removes the device for good."""
    device = _excludable_device()
    coordinator._devices = {device.id: device}

    with patch.object(
        coordinator,
        "send_request",
        AsyncMock(return_value=[Reply(request_id="1", success=True)]),
    ):
        assert await coordinator.async_exclude_device(device.id) is True

    assert device.id not in coordinator._devices
    assert not coordinator._excluding


@pytest.mark.parametrize(
    "outcome",
    [
        TimeoutError(),
        HomeAssistantError("not connected"),
        [Reply(request_id="1", success=False)],
        [
            ErrorMessage(
                metadata=ErrorMetadata(error_source="t"),
                request_id="1",
                success=False,
                payload={},
            )
        ],
        [],
    ],
)
async def test_exclude_failure_keeps_device(
    coordinator: GardenaSmartLocalCoordinator, outcome: object
) -> None:
    """A device the gateway did not release keeps its state."""
    device = _excludable_device()
    coordinator._devices = {device.id: device}
    send = AsyncMock(
        side_effect=outcome if isinstance(outcome, Exception) else None,
        return_value=None if isinstance(outcome, Exception) else outcome,
    )

    with patch.object(coordinator, "send_request", send):
        assert await coordinator.async_exclude_device(device.id) is False

    assert coordinator._devices[device.id] is device
    assert not coordinator._excluding


async def test_discovery_during_exclusion_does_not_restore_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A discovery finishing mid-exclusion must not bring the device back."""
    device = _excludable_device()
    coordinator._devices = {device.id: device}

    async def _send(*args: object, **kwargs: object) -> list[Reply]:
        coordinator._update_devices({device.id: device})
        assert device.id not in coordinator._devices
        return [Reply(request_id="1", success=True)]

    with patch.object(coordinator, "send_request", _send):
        assert await coordinator.async_exclude_device(device.id) is True

    assert device.id not in coordinator._devices


async def test_event_during_exclusion_does_not_schedule_discovery(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Events of a device being excluded are not mistaken for a new device."""
    coordinator._excluding["dev-1"] = _excludable_device()
    event = MagicMock()
    event.entity.path.object_name = "valve"
    event.entity.device = "dev-1"
    event.op = "update"

    assert await coordinator._handle_event(event) is False

    assert coordinator._unknown_device_discovery_handle is None


async def test_event_during_running_rediscovery_queues_one_more_pass(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device announced while a re-discovery runs is picked up by a follow-up."""
    coordinator._unknown_device_discovery_handle = coordinator.hass.loop.call_later(
        99, lambda: None
    )
    running = coordinator.hass.async_create_task(asyncio.sleep(3600))
    coordinator._unknown_device_discovery_task = running

    coordinator._schedule_unknown_device_discovery("dev-2")
    coordinator._schedule_unknown_device_discovery("dev-3")
    assert coordinator._rediscovery_pending is True

    with patch.object(coordinator, "_do_discovery", AsyncMock()):
        await coordinator._discover_unknown_devices()

    assert coordinator._rediscovery_pending is False
    assert coordinator._unknown_device_discovery_handle is not None
    coordinator._unknown_device_discovery_handle.cancel()
    running.cancel()


async def test_event_before_rediscovery_starts_queues_nothing(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A run that has not started yet already covers a new unknown device."""
    coordinator._schedule_unknown_device_discovery("dev-1")
    coordinator._schedule_unknown_device_discovery("dev-2")

    assert coordinator._rediscovery_pending is False
    assert coordinator._unknown_device_discovery_handle is not None
    coordinator._unknown_device_discovery_handle.cancel()


async def test_disconnect_does_not_rearm_rediscovery(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A cancelled run does not schedule its follow-up pass."""
    coordinator._rediscovery_pending = True

    async def _hang() -> None:
        await asyncio.sleep(3600)

    with patch.object(coordinator, "_do_discovery", side_effect=_hang):
        coordinator._unknown_device_discovery_task = coordinator.hass.async_create_task(
            coordinator._discover_unknown_devices()
        )
        await asyncio.sleep(0)
        await coordinator.async_disconnect()

    assert coordinator._unknown_device_discovery_handle is None
    assert coordinator._rediscovery_pending is False


async def test_inclusion_completing_during_last_wait_succeeds(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The device leaving includable state in the final second is a success."""
    info = IncludableDeviceInfo("inst-1", "svc", "dev-1", "Valve", True)
    coordinator._includable_devices["inst-1"] = info

    async def _sleep(_delay: float) -> None:
        coordinator._includable_devices.pop("inst-1", None)

    async def _discover(broadcast: bool = True) -> None:
        coordinator._devices = {"dev-1": MagicMock()}

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.INCLUSION_TIMEOUT",
            1,
        ),
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.asyncio.sleep",
            _sleep,
        ),
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.build_inclusion_obj"
        ),
        patch.object(
            coordinator,
            "send_request",
            AsyncMock(return_value=[Reply(request_id="1", success=True)]),
        ),
        patch.object(coordinator, "_do_discovery", _discover),
    ):
        assert await coordinator.async_include_device("inst-1") == "dev-1"


async def test_inclusion_timeout_when_device_never_leaves(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device still in inclusion mode after the timeout is a failure."""
    info = IncludableDeviceInfo("inst-1", "svc", "dev-1", "Valve", True)
    coordinator._includable_devices["inst-1"] = info

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.INCLUSION_TIMEOUT",
            1,
        ),
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.asyncio.sleep",
            AsyncMock(),
        ),
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.build_inclusion_obj"
        ),
        patch.object(
            coordinator,
            "send_request",
            AsyncMock(return_value=[Reply(request_id="1", success=True)]),
        ),
    ):
        assert await coordinator.async_include_device("inst-1") is None


async def test_discovery_timeout_stays_a_timeout(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A discovery timeout keeps its type so setup treats it as retryable."""
    with (
        patch.object(coordinator, "send_request", AsyncMock(side_effect=TimeoutError)),
        pytest.raises(TimeoutError, match="discovery replies"),
    ):
        await coordinator._do_discovery()


class _FakeWebSocket:
    """Stands in for aiohttp's ClientWebSocketResponse."""

    def __init__(self, messages: list[SimpleNamespace] | None = None) -> None:
        self.closed = False
        self.close_code = 1006
        self.send_str = AsyncMock()
        self._messages = messages or []
        self._iter = iter(self._messages)

    def __aiter__(self) -> _FakeWebSocket:
        self._iter = iter(self._messages)
        return self

    async def __anext__(self) -> SimpleNamespace:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None

    def exception(self) -> Exception:
        return RuntimeError("socket broke")


def _request(*request_ids: str) -> MagicMock:
    request = MagicMock()
    request.root = [MagicMock(request_id=rid) for rid in request_ids]
    request.model_dump_json.return_value = "{}"
    return request


def _event(
    device: str | None = "dev-1",
    op: str = "update",
    object_name: str | None = "valve",
    instance_id: str | None = None,
    service: str | None = None,
    payload: dict | None = None,
) -> MagicMock:
    event = MagicMock()
    event.__class__ = Event
    event.op = op
    event.entity.device = device
    event.entity.path.object_name = object_name
    event.entity.path.object_instance_id = instance_id
    event.entity.service = service
    event.payload = payload or {}
    return event


async def test_connected_reflects_websocket_state(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The coordinator reports a live connection only for an open socket."""
    assert coordinator.connected is False

    coordinator._ws = _FakeWebSocket()
    assert coordinator.connected is True

    coordinator._ws.closed = True
    assert coordinator.connected is False


async def test_send_request_requires_connection(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Sending without a socket fails as a transport error."""
    with pytest.raises(HomeAssistantError, match="not connected"):
        await coordinator.send_request("dev-1", _request("r1"))


async def test_send_request_without_wait_returns_nothing(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A fire-and-forget request is sent and returns no replies."""
    ws = _FakeWebSocket()
    coordinator._ws = ws

    replies = await coordinator.send_request("dev-1", _request("r1"))

    ws.send_str.assert_awaited_once_with("{}")
    assert list(replies) == []


async def test_send_request_returns_matching_replies(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A request waits until every request id has been answered."""
    ws = _FakeWebSocket()
    coordinator._ws = ws
    reply = Reply(request_id="r1", success=True)

    async def _answer(_payload: str) -> None:
        coordinator._pending_replies["r1"].set_result(reply)

    ws.send_str.side_effect = _answer

    replies = await coordinator.send_request(
        "dev-1", _request("r1"), wait_for_response_sec=1
    )

    assert list(replies) == [reply]
    assert not coordinator._pending_replies


async def test_send_request_times_out_and_cleans_up(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An unanswered request raises and leaves no pending future behind."""
    coordinator._ws = _FakeWebSocket()

    with pytest.raises(TimeoutError):
        await coordinator.send_request(
            "dev-1", _request("r1"), wait_for_response_sec=0.01
        )

    assert not coordinator._pending_replies


async def test_ws_reader_queues_frames_until_closed(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Text and binary frames are queued, and a closed frame ends the reader."""
    ws = _FakeWebSocket(
        [
            SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data="text"),
            SimpleNamespace(type=aiohttp.WSMsgType.BINARY, data=b"binary"),
            SimpleNamespace(type=aiohttp.WSMsgType.CLOSED, data=None),
            SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data="never read"),
        ]
    )

    await coordinator._ws_reader(ws)

    assert coordinator._msg_queue.get_nowait() == "text"
    assert coordinator._msg_queue.get_nowait() == "binary"
    assert coordinator._msg_queue.empty()


async def test_ws_reader_stops_on_socket_error(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A socket error ends the reader so the loop reconnects."""
    ws = _FakeWebSocket(
        [
            SimpleNamespace(type=aiohttp.WSMsgType.ERROR, data=None),
            SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data="never read"),
        ]
    )

    await coordinator._ws_reader(ws)

    assert coordinator._msg_queue.empty()


async def _run_consumer(coordinator: GardenaSmartLocalCoordinator) -> asyncio.Task:
    task = asyncio.get_running_loop().create_task(coordinator._msg_consumer())
    await asyncio.sleep(0)
    return task


async def _stop(task: asyncio.Task) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def test_msg_consumer_resolves_reply_and_forwards_the_rest(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Replies resolve their waiter, everything else goes to the event handler."""
    fut = asyncio.get_running_loop().create_future()
    coordinator._pending_replies["r1"] = fut
    answered = Reply(request_id="r1", success=True)
    unrelated = Reply(request_id="other", success=True)
    coordinator._msg_queue.put_nowait(
        IngressMessageList([answered, unrelated]).model_dump_json()
    )
    handled = AsyncMock()

    with patch.object(coordinator, "_handle_messages", handled):
        task = await _run_consumer(coordinator)
        assert await asyncio.wait_for(fut, 1) == answered
        await asyncio.sleep(0)
        await _stop(task)

    handled.assert_awaited_once()
    assert list(handled.await_args.args[0]) == [unrelated]


async def test_msg_consumer_ignores_malformed_frames(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A frame that is not a message list is skipped without stopping the consumer."""
    coordinator._msg_queue.put_nowait("not json")
    coordinator._msg_queue.put_nowait(
        IngressMessageList([Reply(request_id="x", success=True)]).model_dump_json()
    )
    handled = AsyncMock()

    with patch.object(coordinator, "_handle_messages", handled):
        task = await _run_consumer(coordinator)
        await asyncio.sleep(0)
        await _stop(task)

    handled.assert_awaited_once()


async def test_msg_consumer_reraises_handler_failure(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A failing handler stops the consumer so the loop reconnects."""
    coordinator._msg_queue.put_nowait(
        IngressMessageList([Reply(request_id="x", success=True)]).model_dump_json()
    )

    with patch.object(
        coordinator, "_handle_messages", AsyncMock(side_effect=RuntimeError("boom"))
    ):
        task = await _run_consumer(coordinator)
        with pytest.raises(RuntimeError, match="boom"):
            await asyncio.wait_for(task, 1)


async def test_handle_messages_publishes_changes_once(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Only events that changed state publish new data, and one bad event is skipped."""
    changed = _event()
    failing = _event(device="dev-2")
    unchanged = _event(device="dev-3")
    results = {
        id(changed): True,
        id(failing): RuntimeError("bad event"),
        id(unchanged): False,
    }

    async def _handle(event: Event) -> bool:
        result = results[id(event)]
        if isinstance(result, Exception):
            raise result
        return result

    messages = IngressMessageList([])
    messages.root = [changed, Reply(request_id="r", success=True), failing, unchanged]
    updated = MagicMock()

    with (
        patch.object(coordinator, "_handle_event", _handle),
        patch.object(coordinator, "async_set_updated_data", updated),
    ):
        await coordinator._handle_messages(messages)

    updated.assert_called_once_with(coordinator._devices)


async def test_handle_event_routes_includable_events(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Includable device events go to the inclusion tracking."""
    event = _event(object_name="includable_device")

    with patch.object(coordinator, "_handle_includable_event", AsyncMock()) as handle:
        assert await coordinator._handle_event(event) is False

    handle.assert_awaited_once_with(event)


async def test_handle_event_ignores_events_without_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An event that names no device cannot be applied."""
    assert await coordinator._handle_event(_event(device=None)) is False


async def test_handle_event_delete_drops_known_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A delete event for the whole device removes it from the map."""
    coordinator._devices = {"dev-1": MagicMock()}

    assert (
        await coordinator._handle_event(_event(op="delete", object_name=None)) is False
    )

    assert "dev-1" not in coordinator._devices


async def test_handle_event_unknown_device_schedules_discovery(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An update for an unknown device triggers a re-discovery, a delete does not."""
    assert await coordinator._handle_event(_event(op="delete")) is False
    assert coordinator._unknown_device_discovery_handle is None

    assert await coordinator._handle_event(_event(op="update")) is False

    assert coordinator._unknown_device_discovery_handle is not None
    coordinator._unknown_device_discovery_handle.cancel()


async def test_handle_event_updates_known_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An update for a known device is applied to it."""
    device = MagicMock()
    device.is_online = True
    coordinator._devices = {"dev-1": device}
    event = _event()

    def _go_offline(_event: Event) -> None:
        device.is_online = False

    device.update_data.side_effect = _go_offline

    assert await coordinator._handle_event(event) is True

    device.update_data.assert_called_once_with(event)


async def test_includable_event_without_instance_is_ignored(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An includable event without an instance id cannot be tracked."""
    await coordinator._handle_includable_event(_event(instance_id=None))

    assert not coordinator._includable_devices
    assert not coordinator._includable_timeouts


async def test_includable_event_delete_forgets_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A delete event removes the device and cancels its heartbeat timeout."""
    handle = MagicMock()
    coordinator._includable_timeouts["inst-1"] = handle
    coordinator._includable_devices["inst-1"] = IncludableDeviceInfo(
        "inst-1", "svc", "dev-1", "Valve", True
    )

    await coordinator._handle_includable_event(
        _event(op="delete", instance_id="inst-1")
    )

    handle.cancel.assert_called_once()
    assert not coordinator._includable_devices
    assert not coordinator._includable_timeouts


@pytest.mark.parametrize(
    ("service", "payload"),
    [
        (None, {"identifier": {"vs": "abc"}}),
        ("svc", {}),
    ],
)
async def test_includable_event_without_service_or_identifier(
    coordinator: GardenaSmartLocalCoordinator,
    service: str | None,
    payload: dict,
) -> None:
    """An event that cannot identify the device is not tracked as includable."""
    await coordinator._handle_includable_event(
        _event(instance_id="inst-1", service=service, payload=payload)
    )

    assert not coordinator._includable_devices
    coordinator._includable_timeouts["inst-1"].cancel()


async def test_includable_event_with_unparsable_identifier(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An identifier that is not an SGTIN is ignored."""
    await coordinator._handle_includable_event(
        _event(
            instance_id="inst-1", service="svc", payload={"identifier": {"vs": "nope"}}
        )
    )

    assert not coordinator._includable_devices
    coordinator._includable_timeouts["inst-1"].cancel()


async def test_includable_event_tracks_supported_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A valid event registers the device, and a heartbeat only re-arms the timeout."""
    sgtin = MagicMock(item_reference=1, serial=5)
    sgtin.get_model_name = AsyncMock(return_value="Water Control")
    event = _event(
        instance_id="inst-1", service="svc", payload={"identifier": {"vs": "abc"}}
    )

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.SGTIN96Info"
        ) as sgtin_info,
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.MODEL_NUMBER_MAP",
            {1: Gen2WaterControl},
        ),
    ):
        sgtin_info.from_hex.return_value = sgtin
        await coordinator._handle_includable_event(event)
        await coordinator._handle_includable_event(event)

    assert coordinator.includable_devices == {
        "inst-1": IncludableDeviceInfo(
            "inst-1", "svc", "abc", "Water Control 00000005", True
        )
    }
    sgtin_info.from_hex.assert_called_once_with("abc")
    coordinator._includable_timeouts["inst-1"].cancel()


async def test_includable_device_expires_without_heartbeat(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device that stops announcing itself is forgotten."""
    coordinator._includable_devices["inst-1"] = IncludableDeviceInfo(
        "inst-1", "svc", "dev-1", "Valve", True
    )
    coordinator._includable_timeouts["inst-1"] = MagicMock()

    coordinator._expire_includable("inst-1")

    assert not coordinator._includable_devices
    assert not coordinator._includable_timeouts


async def test_includable_devices_lists_supported_only(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Unsupported devices are tracked but not offered for inclusion."""
    coordinator._includable_devices["a"] = IncludableDeviceInfo(
        "a", "s", "d1", "A", True
    )
    coordinator._includable_devices["b"] = IncludableDeviceInfo(
        "b", "s", "d2", "B", False
    )

    assert list(coordinator.includable_devices) == ["a"]


@pytest.mark.parametrize(
    ("instance_id", "supported"), [("missing", True), ("inst-1", False)]
)
async def test_include_rejects_unknown_or_unsupported_device(
    coordinator: GardenaSmartLocalCoordinator, instance_id: str, supported: bool
) -> None:
    """Only a known, supported device can be included."""
    coordinator._includable_devices["inst-1"] = IncludableDeviceInfo(
        "inst-1", "svc", "dev-1", "Valve", supported
    )

    assert await coordinator.async_include_device(instance_id) is None


@pytest.mark.parametrize(
    "outcome",
    [
        TimeoutError(),
        HomeAssistantError("not connected"),
        [
            ErrorMessage(
                metadata=ErrorMetadata(error_source="t"),
                request_id="1",
                success=False,
                payload={},
            )
        ],
        [Reply(request_id="1", success=False)],
    ],
)
async def test_include_fails_when_gateway_refuses(
    coordinator: GardenaSmartLocalCoordinator, outcome: object
) -> None:
    """A failed or rejected inclusion request reports failure."""
    coordinator._includable_devices["inst-1"] = IncludableDeviceInfo(
        "inst-1", "svc", "dev-1", "Valve", True
    )
    send = AsyncMock(
        side_effect=outcome if isinstance(outcome, Exception) else None,
        return_value=None if isinstance(outcome, Exception) else outcome,
    )

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.build_inclusion_obj"
        ),
        patch.object(coordinator, "send_request", send),
    ):
        assert await coordinator.async_include_device("inst-1") is None

    assert not coordinator._including_device_ids


async def test_include_fails_when_discovery_does_not_find_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device missing from the post-inclusion discovery is a failure."""
    coordinator._includable_devices["inst-1"] = IncludableDeviceInfo(
        "inst-1", "svc", "dev-1", "Valve", True
    )

    async def _send(*args: object, **kwargs: object) -> list[Reply]:
        # The gateway takes the device out of inclusion mode right away.
        coordinator._includable_devices.pop("inst-1")
        return [Reply(request_id="1", success=True)]

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.build_inclusion_obj"
        ),
        patch.object(coordinator, "send_request", _send),
        patch.object(coordinator, "_do_discovery", AsyncMock()),
    ):
        assert await coordinator.async_include_device("inst-1") is None


async def test_include_fails_when_rediscovery_errors(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A failing post-inclusion discovery reports failure."""
    coordinator._includable_devices["inst-1"] = IncludableDeviceInfo(
        "inst-1", "svc", "dev-1", "Valve", True
    )

    async def _leave(_delay: float) -> None:
        coordinator._includable_devices.pop("inst-1", None)

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.build_inclusion_obj"
        ),
        patch.object(
            coordinator,
            "send_request",
            AsyncMock(return_value=[Reply(request_id="1", success=True)]),
        ),
        patch.object(
            coordinator, "_do_discovery", AsyncMock(side_effect=RuntimeError("boom"))
        ),
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.asyncio.sleep",
            _leave,
        ),
    ):
        assert await coordinator.async_include_device("inst-1") is None


async def test_drop_unknown_device_changes_nothing(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Dropping a device the map does not hold publishes nothing."""
    updated = MagicMock()
    with patch.object(coordinator, "async_set_updated_data", updated):
        coordinator.async_drop_device("dev-1")

    updated.assert_not_called()


async def test_update_devices_replaces_the_map(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A full discovery adds new devices, refreshes known ones and drops gone ones."""
    gone, kept, new = MagicMock(id="gone"), MagicMock(id="kept"), MagicMock(id="new")
    coordinator._devices = {"gone": gone, "kept": kept}
    refreshed = MagicMock(id="kept")

    coordinator._update_devices({"kept": refreshed, "new": new})

    assert coordinator._devices == {"kept": refreshed, "new": new}


async def test_update_devices_survives_a_broken_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device that cannot be applied does not block the devices after it."""
    broken, healthy = MagicMock(id="broken"), MagicMock(id="healthy")
    original = coordinator._update_device

    def _update(device: MagicMock) -> None:
        if device is broken:
            raise RuntimeError("bad")
        original(device)

    with patch.object(coordinator, "_update_device", side_effect=_update):
        coordinator._update_devices({"broken": broken, "healthy": healthy})

    assert list(coordinator._devices.keys()) == ["healthy"]


async def test_ws_loop_connects_runs_discovery_and_reconnects(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The loop reports the first connection, then reconnects after a failure."""
    ws = _FakeWebSocket()
    connection = MagicMock()
    connection.__aenter__ = AsyncMock(return_value=ws)
    connection.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.ws_connect.side_effect = [
        aiohttp.ClientConnectionError("gone"),
        connection,
        connection,
    ]

    async def _reader_ends(_ws: object) -> None:
        return

    async def _consumer_waits() -> None:
        await asyncio.sleep(3600)

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.RECONNECT_DELAY",
            0,
        ),
        patch.object(coordinator, "_ws_reader", _reader_ends),
        patch.object(coordinator, "_msg_consumer", _consumer_waits),
        patch.object(coordinator, "_do_discovery", AsyncMock()) as discovery,
    ):
        coordinator._first_connect_result = asyncio.get_running_loop().create_future()
        task = asyncio.get_running_loop().create_task(coordinator._ws_loop())
        for _ in range(50):
            await asyncio.sleep(0)
            if discovery.await_count >= 2:
                break
        await _stop(task)

    assert session.ws_connect.call_count >= 3
    assert discovery.await_count >= 2
    assert coordinator._first_connect_result.done()
    assert coordinator._outage_logged is False
    assert coordinator.connected is False


async def test_connect_waits_for_first_discovery(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """async_connect returns once the loop reports its first successful connection."""

    async def _loop() -> None:
        coordinator._first_connect_result.set_result(None)
        await asyncio.sleep(3600)

    with patch.object(coordinator, "_ws_loop", _loop):
        await coordinator.async_connect()
        await coordinator.async_disconnect()

    assert coordinator._first_connect_result.done()


async def test_update_data_returns_the_device_map(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Refreshing returns the pushed state instead of polling."""
    assert await coordinator._async_update_data() is coordinator._devices


async def test_disconnect_cancels_includable_timeouts(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Disconnecting stops the heartbeat timers of includable devices."""
    handle = MagicMock()
    coordinator._includable_timeouts["inst-1"] = handle

    await coordinator.async_disconnect()

    handle.cancel.assert_called_once()
    assert not coordinator._includable_timeouts


async def test_start_unknown_device_discovery_runs_a_task(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The debounce timer starts the re-discovery as a task."""
    with patch.object(coordinator, "_do_discovery", AsyncMock()) as discovery:
        coordinator._start_unknown_device_discovery()
        assert coordinator._unknown_device_discovery_task is not None
        await coordinator._unknown_device_discovery_task

    discovery.assert_awaited_once()


@pytest.mark.parametrize("broadcast", [True, False])
async def test_do_discovery_applies_the_result(
    coordinator: GardenaSmartLocalCoordinator, broadcast: bool
) -> None:
    """A discovery replaces the device map and publishes it when asked to."""
    device = MagicMock(id="dev-1")
    updated = MagicMock()

    with (
        patch.object(coordinator, "send_request", AsyncMock(return_value=[])),
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.create_devices_from_messages",
            AsyncMock(return_value={"dev-1": device}),
        ),
        patch.object(coordinator, "async_set_updated_data", updated),
    ):
        await coordinator._do_discovery(broadcast=broadcast)

    assert dict(coordinator._devices.items()) == {"dev-1": device}
    assert updated.called is broadcast


async def test_failed_connect_fails_waiters_and_the_first_connect(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A lost connection fails pending requests and the initial connect wait."""
    session = MagicMock()
    session.ws_connect.side_effect = aiohttp.ClientConnectionError("gone")
    pending = asyncio.get_running_loop().create_future()
    coordinator._pending_replies["r1"] = pending
    coordinator._first_connect_result = asyncio.get_running_loop().create_future()
    coordinator._outage_logged = True

    with patch(
        "homeassistant.components.gardena_smart_local.coordinator.async_get_clientsession",
        return_value=session,
    ):
        task = asyncio.get_running_loop().create_task(coordinator._ws_loop())
        for _ in range(10):
            await asyncio.sleep(0)
        await _stop(task)

    with pytest.raises(aiohttp.ClientConnectionError):
        coordinator._first_connect_result.result()
    with pytest.raises(HomeAssistantError, match="disconnected"):
        pending.result()
    assert not coordinator._pending_replies


def _rejected_password() -> aiohttp.WSServerHandshakeError:
    """Return the error aiohttp raises when the gateway answers 401."""
    return aiohttp.WSServerHandshakeError(MagicMock(), (), status=401)


async def test_ws_loop_starts_reauth_when_password_changes(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A 401 on reconnect starts reauthentication and stops retrying."""
    session = MagicMock()
    session.ws_connect.side_effect = _rejected_password()
    coordinator._first_connect_result = asyncio.get_running_loop().create_future()
    coordinator._first_connect_result.set_result(None)

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.async_get_clientsession",
            return_value=session,
        ),
        patch.object(coordinator.config_entry, "async_start_reauth") as start_reauth,
    ):
        await asyncio.wait_for(coordinator._ws_loop(), timeout=1)

    start_reauth.assert_called_once_with(coordinator.hass)
    session.ws_connect.assert_called_once()


async def test_ws_loop_reports_rejected_password_to_setup(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A 401 on the first connection is left to setup, which owns reauth."""
    session = MagicMock()
    session.ws_connect.side_effect = _rejected_password()
    coordinator._first_connect_result = asyncio.get_running_loop().create_future()

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.async_get_clientsession",
            return_value=session,
        ),
        patch.object(coordinator.config_entry, "async_start_reauth") as start_reauth,
    ):
        await asyncio.wait_for(coordinator._ws_loop(), timeout=1)

    with pytest.raises(aiohttp.WSServerHandshakeError):
        coordinator._first_connect_result.result()
    start_reauth.assert_not_called()
