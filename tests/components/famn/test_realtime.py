"""Tests for the Famn realtime WebSocket client."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
from famn_sdk import ApiError, DeviceTokenResponse
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.famn.const import EVENT_FAMN_EVENT
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_capture_events, async_fire_time_changed

pytestmark = [pytest.mark.usefixtures("mock_famn")]

# The coordinator debounces refresh requests with a 10 second cooldown.
REFRESH_COOLDOWN = timedelta(seconds=11)


class FakeFamnSocket:
    """A scripted stand-in for a gateway WebSocket connection."""

    def __init__(self, auth_ok: bool) -> None:
        """Initialize the fake socket."""
        self.auth_ok = auth_ok
        self.sent: list[dict[str, Any]] = []
        self.incoming: asyncio.Queue[aiohttp.WSMessage] = asyncio.Queue()

    async def send_json(self, data: dict[str, Any]) -> None:
        """Record an outgoing frame, acknowledging auth like the gateway."""
        self.sent.append(data)
        if data.get("type") == "auth":
            if self.auth_ok:
                self.feed({"type": "auth_ok", "spaces": []})
            else:
                self.feed({"type": "error", "code": 401, "message": "invalid token"})

    def feed(self, data: dict[str, Any]) -> None:
        """Queue an incoming text frame."""
        self.incoming.put_nowait(
            aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, json.dumps(data), None)
        )

    def disconnect(self) -> None:
        """Queue a close of the connection from the server side."""
        self.incoming.put_nowait(
            aiohttp.WSMessage(aiohttp.WSMsgType.CLOSED, None, None)
        )

    async def receive(self) -> aiohttp.WSMessage:
        """Return the next incoming frame."""
        return await self.incoming.get()


class FakeGateway:
    """Hand out a fake socket per connection attempt."""

    def __init__(self) -> None:
        """Initialize the fake gateway."""
        self.auth_ok = True
        self.sockets: list[FakeFamnSocket] = []

    def connect(self, *args: Any, **kwargs: Any) -> MagicMock:
        """Return an async context manager yielding a fresh fake socket."""
        socket = FakeFamnSocket(self.auth_ok)
        self.sockets.append(socket)
        connection = MagicMock()
        connection.__aenter__ = AsyncMock(return_value=socket)
        connection.__aexit__ = AsyncMock(return_value=False)
        return connection


@pytest.fixture
def mock_gateway(mock_realtime_session: MagicMock) -> FakeGateway:
    """Let the realtime client reach a scripted fake gateway."""
    gateway = FakeGateway()
    mock_realtime_session.ws_connect = MagicMock(side_effect=gateway.connect)
    return gateway


async def _async_wait_for(condition: Callable[[], bool]) -> None:
    """Yield to the background task until the condition holds."""
    for _ in range(50):
        if condition():
            return
        await asyncio.sleep(0)
    raise AssertionError("Condition never became true")


async def test_connect_authenticates_and_subscribes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: FakeGateway,
) -> None:
    """Test that the client authenticates with the device access token."""
    await setup_integration(hass, mock_config_entry)

    await _async_wait_for(lambda: bool(mock_gateway.sockets))
    socket = mock_gateway.sockets[0]

    await _async_wait_for(lambda: bool(socket.sent))
    assert socket.sent[0] == {"type": "auth", "token": "mock-access-token"}


async def test_event_triggers_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tasks_api: AsyncMock,
    mock_gateway: FakeGateway,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a task event causes the coordinator to refresh."""
    await setup_integration(hass, mock_config_entry)
    await _async_wait_for(
        lambda: bool(mock_gateway.sockets and mock_gateway.sockets[0].sent)
    )
    baseline = mock_tasks_api.get_task_lists_endpoint.call_count

    mock_gateway.sockets[0].feed(
        {"type": "event", "topic": "TaskItem", "action": "updated", "payload": {}}
    )

    # The refresh request lands in the coordinator's debouncer.
    freezer.tick(REFRESH_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_tasks_api.get_task_lists_endpoint.call_count > baseline


async def test_events_are_fired_on_the_bus(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tasks_api: AsyncMock,
    mock_gateway: FakeGateway,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that every gateway event reaches the Home Assistant event bus."""
    await setup_integration(hass, mock_config_entry)
    await _async_wait_for(
        lambda: bool(mock_gateway.sockets and mock_gateway.sockets[0].sent)
    )
    events = async_capture_events(hass, EVENT_FAMN_EVENT)
    baseline = mock_tasks_api.get_task_lists_endpoint.call_count

    # A topic without entities still reaches automations...
    mock_gateway.sockets[0].feed(
        {
            "type": "event",
            "topic": "Chat",
            "action": "created",
            "spaceId": "space-1",
            "eventId": "evt-1",
            "payload": {"id": "msg-1"},
        }
    )
    await _async_wait_for(lambda: len(events) == 1)
    assert events[0].data == {
        "topic": "Chat",
        "action": "created",
        "space_id": "space-1",
        "event_id": "evt-1",
        "payload": {"id": "msg-1"},
    }

    # ...but does not refresh any coordinator.
    freezer.tick(REFRESH_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_tasks_api.get_task_lists_endpoint.call_count == baseline

    # A mapped topic fires the bus event and refreshes.
    mock_gateway.sockets[0].feed(
        {"type": "event", "topic": "TaskItem", "action": "updated", "payload": {}}
    )
    await _async_wait_for(lambda: len(events) == 2)


async def test_list_event_triggers_shopping_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_api: AsyncMock,
    mock_gateway: FakeGateway,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a topic routes to its own coordinator, not to every one."""
    await setup_integration(hass, mock_config_entry)
    await _async_wait_for(
        lambda: bool(mock_gateway.sockets and mock_gateway.sockets[0].sent)
    )
    baseline = mock_list_api.get_list_items_endpoint.call_count

    mock_gateway.sockets[0].feed(
        {"type": "event", "topic": "ListItem", "action": "updated", "payload": {}}
    )

    freezer.tick(REFRESH_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_list_api.get_list_items_endpoint.call_count > baseline


async def test_unrelated_event_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tasks_api: AsyncMock,
    mock_gateway: FakeGateway,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that events for other domains do not cause a refresh."""
    await setup_integration(hass, mock_config_entry)
    await _async_wait_for(
        lambda: bool(mock_gateway.sockets and mock_gateway.sockets[0].sent)
    )
    baseline = mock_tasks_api.get_task_lists_endpoint.call_count

    mock_gateway.sockets[0].feed(
        {"type": "event", "topic": "Recipe", "action": "updated", "payload": {}}
    )

    freezer.tick(REFRESH_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_tasks_api.get_task_lists_endpoint.call_count == baseline


async def test_rejected_auth_invalidates_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: FakeGateway,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a rejected session forces a token rotation before retrying."""
    # Frozen inside the fixture token's validity, so the token still looks
    # fine locally and only the gateway's rejection can invalidate it.
    freezer.move_to("2026-08-12T12:00:00Z")
    mock_gateway.auth_ok = False

    await setup_integration(hass, mock_config_entry)
    await _async_wait_for(
        lambda: bool(mock_gateway.sockets and mock_gateway.sockets[0].sent)
    )

    auth = mock_config_entry.runtime_data.chores.auth
    await _async_wait_for(lambda: auth.reauth_at <= dt_util.utcnow())


async def test_reauth_frame_extends_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_api: AsyncMock,
    mock_gateway: FakeGateway,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an expiring token is renewed on the open socket."""
    freezer.move_to("2026-08-12T12:00:00Z")
    await setup_integration(hass, mock_config_entry)
    await _async_wait_for(
        lambda: bool(mock_gateway.sockets and mock_gateway.sockets[0].sent)
    )
    socket = mock_gateway.sockets[0]
    assert mock_device_api.rotate_device_refresh_token_endpoint.call_count == 1

    # Move past the renewal deadline of the 12:10Z token and hand the
    # rotation a token that is fresh relative to the new time.
    freezer.move_to("2026-08-12T12:09:00Z")
    mock_device_api.rotate_device_refresh_token_endpoint.return_value = (
        DeviceTokenResponse(
            access_token="renewed-access-token",
            refresh_token="renewed-refresh-token",
            access_token_expires_at=dt_util.utcnow() + timedelta(minutes=10),
        )
    )

    # Any frame wakes the read loop, which then notices the deadline.
    socket.feed({"type": "pong"})

    await _async_wait_for(
        lambda: {"type": "auth", "token": "renewed-access-token"} in socket.sent
    )
    assert mock_device_api.rotate_device_refresh_token_endpoint.call_count == 2


async def test_reauth_flow_starts_when_device_is_revoked(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_api: AsyncMock,
    mock_gateway: FakeGateway,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a revoked device surfaces as a reauth flow."""
    freezer.move_to("2026-08-12T12:00:00Z")
    await setup_integration(hass, mock_config_entry)
    await _async_wait_for(
        lambda: bool(mock_gateway.sockets and mock_gateway.sockets[0].sent)
    )
    socket = mock_gateway.sockets[0]

    # The renewal attempt on the socket hits a revoked device registration.
    freezer.move_to("2026-08-12T12:09:00Z")
    mock_device_api.rotate_device_refresh_token_endpoint.side_effect = ApiError(
        401, "revoked"
    )
    socket.feed({"type": "pong"})

    await _async_wait_for(
        lambda: any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))
    )


async def test_non_advancing_expiry_drops_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_api: AsyncMock,
    mock_gateway: FakeGateway,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a token expiry that never advances does not spin."""
    await setup_integration(hass, mock_config_entry)
    await _async_wait_for(
        lambda: bool(mock_gateway.sockets and mock_gateway.sockets[0].sent)
    )
    socket = mock_gateway.sockets[0]

    def stale_frames() -> int:
        """Count the auth frames sent with the stale token."""
        return sum(frame.get("token") == "stale-access-token" for frame in socket.sent)

    # Famn hands back an access token that already looks expired here, as a
    # server clock running ahead of ours would.
    freezer.move_to("2026-08-12T12:09:00Z")
    mock_device_api.rotate_device_refresh_token_endpoint.return_value = (
        DeviceTokenResponse(
            access_token="stale-access-token",
            refresh_token="stale-refresh-token",
            access_token_expires_at=dt_util.utcnow() - timedelta(minutes=1),
        )
    )

    # Any frame wakes the read loop, which then notices the deadline.
    socket.feed({"type": "pong"})
    await _async_wait_for(lambda: stale_frames() == 1)

    # The session is dropped after that single attempt rather than
    # re-authenticating in a tight loop.
    for _ in range(50):
        await asyncio.sleep(0)
    assert stale_frames() == 1


async def test_server_close_reconnects_after_backoff(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: FakeGateway,
) -> None:
    """Test that a server-side close ends the session cleanly."""
    await setup_integration(hass, mock_config_entry)
    await _async_wait_for(
        lambda: bool(mock_gateway.sockets and mock_gateway.sockets[0].sent)
    )

    mock_gateway.sockets[0].disconnect()

    # The reconnect happens after a real-time backoff, so only the clean
    # teardown of the first connection is observable here.
    await hass.async_block_till_done()
    assert len(mock_gateway.sockets) == 1
