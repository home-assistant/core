"""Test the Litter-Robot camera entity."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from pylitterbot.camera import CameraSession
from pylitterbot.exceptions import CameraNotAvailableException, CameraStreamException
import pytest
from pytest_homeassistant.common import async_fire_time_changed, snapshot_platform
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    CameraState,
    StreamType,
    async_get_image,
    get_camera_from_entity_id,
)
from homeassistant.components.litterrobot.camera import _build_ice_servers
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import create_mock_robot, setup_integration

# the LR5 Pro fixture's robot is named "Test Pro", not "Test"
CAMERA_ENTITY_ID = "camera.test_pro_camera"
RELAY = "homeassistant.components.litterrobot.camera.CameraSignalingRelay"

TURN_URL = "turn:turn.example.com:443?transport=tcp"
MOCK_SESSION_DATA = {
    "sessionId": "test-session-id",
    "sessionToken": "test-session-token",
    # far future on purpose: a fixed near date silently flips these tests
    # onto the expired-session branch once it passes
    "sessionExpiration": "2099-12-31T23:59:59.000000Z",
    "turnCredentials": [
        {"urls": [TURN_URL], "username": "turn-user", "credential": "turn-pass"}
    ],
}
NETWORK_ERRORS = [
    CameraStreamException("refused"),
    ClientError("refused"),
    TimeoutError("refused"),
]


def _session(**overrides: Any) -> CameraSession:
    """Build a camera session, optionally overriding response fields."""
    return CameraSession.from_response({**MOCK_SESSION_DATA, **overrides})


def _expiring_in(seconds: int) -> str:
    """Return a session expiration timestamp relative to now."""
    return (dt_util.utcnow() + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def _relay(start: Callable[..., Any] | None = None) -> MagicMock:
    """Build a signaling relay mock whose start() returns a session."""
    relay = MagicMock()
    relay.start = AsyncMock(side_effect=start, return_value=_session())
    relay.send_candidate = AsyncMock()
    relay.close = AsyncMock()
    return relay


@pytest.fixture
def camera_client(mock_account_with_litterrobot_5_pro: MagicMock) -> MagicMock:
    """Return the robot's camera client, handing out valid sessions."""
    client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    client.generate_session = AsyncMock(return_value=_session())
    return client


async def _setup(hass: HomeAssistant, account: MagicMock) -> None:
    """Set up the integration and let the startup session fetch finish."""
    await setup_integration(hass, account, CAMERA_DOMAIN)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _send_offer(client: MockHAClientWebSocket) -> tuple[int, str]:
    """Send an offer and return the subscription id and the session id."""
    await client.send_json_auto_id(
        {"type": "camera/webrtc/offer", "entity_id": CAMERA_ENTITY_ID, "offer": "v=0"}
    )
    response = await client.receive_json()
    assert response["success"] is True
    subscription_id = response["id"]

    response = await client.receive_json()
    assert response["event"]["type"] == "session"
    return subscription_id, response["event"]["session_id"]


async def _send_candidate(
    client: MockHAClientWebSocket, session_id: str, candidate: dict[str, Any]
) -> None:
    """Send a browser candidate for a session."""
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": CAMERA_ENTITY_ID,
            "session_id": session_id,
            "candidate": candidate,
        }
    )
    response = await client.receive_json()
    assert response["success"] is True


async def _unsubscribe(client: MockHAClientWebSocket, subscription_id: int) -> None:
    """Close the browser's session."""
    await client.send_json_auto_id(
        {"type": "unsubscribe_events", "subscription": subscription_id}
    )
    response = await client.receive_json()
    assert response["success"] is True


async def _ice_servers(client: MockHAClientWebSocket) -> list[dict[str, Any]]:
    """Return the ICE servers the camera adds to the frontend's configuration."""
    await client.send_json_auto_id(
        {"type": "camera/webrtc/get_client_config", "entity_id": CAMERA_ENTITY_ID}
    )
    response = await client.receive_json()
    assert response["success"] is True
    # leave out the STUN servers Home Assistant adds to every camera
    return [
        server
        for server in response["result"]["configuration"]["iceServers"]
        if "stun.home-assistant.io" not in str(server["urls"])
    ]


def _state(hass: HomeAssistant) -> str:
    """Return the camera entity's state."""
    state = hass.states.get(CAMERA_ENTITY_ID)
    assert state is not None
    return state.state


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "camera_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_account_with_litterrobot_5_pro: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Litter-Robot 5 Pro camera entities."""
    with (
        patch("homeassistant.components.litterrobot.PLATFORMS", [Platform.CAMERA]),
        # keeps the access token in the state attributes stable
        patch(
            "homeassistant.components.camera.entity.SystemRandom.getrandbits",
            return_value=123123123123,
        ),
    ):
        entry = await setup_integration(hass, mock_account_with_litterrobot_5_pro)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("camera_client")
async def test_camera_supports_native_webrtc(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """The camera streams over WebRTC and is idle until someone watches."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)

    camera = get_camera_from_entity_id(hass, CAMERA_ENTITY_ID)
    assert camera.camera_capabilities.frontend_stream_types == {StreamType.WEB_RTC}
    assert _state(hass) == CameraState.IDLE


async def test_camera_not_created_for_standard_lr5(
    hass: HomeAssistant, mock_account_with_litterrobot_5: MagicMock
) -> None:
    """Test camera entity is not created for standard LR5 (no camera)."""
    await setup_integration(hass, mock_account_with_litterrobot_5, CAMERA_DOMAIN)

    # assert on the domain rather than a guessed entity id: a wrong id would
    # make this pass whether or not an entity was created
    assert not hass.states.async_entity_ids(CAMERA_DOMAIN)


async def test_camera_not_created_for_lr3(
    hass: HomeAssistant, mock_account: MagicMock
) -> None:
    """Test camera entity is not created for LR3."""
    await setup_integration(hass, mock_account, CAMERA_DOMAIN)

    assert not hass.states.async_entity_ids(CAMERA_DOMAIN)


@pytest.mark.usefixtures("camera_client")
async def test_camera_image_is_a_placeholder(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """No snapshot endpoint exists, so a placeholder still is served."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)

    image = await async_get_image(hass, CAMERA_ENTITY_ID)
    assert image.content_type == "image/png"
    assert image.content.startswith(b"\x89PNG\r\n\x1a\n")


async def test_startup_fetches_turn_credentials_without_waking_the_camera(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    camera_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A session is fetched once at startup and reused while it is valid."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)

    camera_client.generate_session.assert_awaited_once_with(auto_start=False)
    (server,) = await _ice_servers(client)
    assert server == {
        "urls": [TURN_URL],
        "username": "turn-user",
        "credential": "turn-pass",
    }
    # a valid session is not fetched again
    assert camera_client.generate_session.await_count == 1


async def test_webrtc_session(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    camera_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """An offer relays signaling both ways; closing the session tears it down."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)

    async def start(offer_sdp, on_answer, on_candidate):
        on_answer("answer-sdp")
        on_candidate({"candidate": "candidate:a", "sdpMid": "1", "sdpMLineIndex": 2})
        # a candidate without the optional fields gets the defaults
        on_candidate({})
        return _session()

    relay = _relay(start)
    with patch(RELAY, return_value=relay) as relay_class:
        subscription_id, session_id = await _send_offer(client)

    relay_class.assert_called_once_with(camera_client)
    assert relay.start.call_args.args[0] == "v=0"
    for expected in (
        {"type": "answer", "answer": "answer-sdp"},
        {
            "type": "candidate",
            "candidate": {
                "candidate": "candidate:a",
                "sdpMid": "1",
                "sdpMLineIndex": 2,
            },
        },
        {
            "type": "candidate",
            "candidate": {"candidate": "", "sdpMid": "0", "sdpMLineIndex": 0},
        },
    ):
        response = await client.receive_json()
        assert response["id"] == subscription_id
        assert response["event"] == expected
    assert _state(hass) == CameraState.STREAMING

    # browser candidates are forwarded to the camera
    await _send_candidate(
        client,
        session_id,
        {"candidate": "candidate:1", "sdpMid": "1", "sdpMLineIndex": 3},
    )
    relay.send_candidate.assert_awaited_with(
        {"candidate": "candidate:1", "sdpMid": "1", "sdpMLineIndex": 3}
    )
    # a candidate without mid or index targets the first media section
    await _send_candidate(client, session_id, {"candidate": "candidate:2"})
    relay.send_candidate.assert_awaited_with(
        {"candidate": "candidate:2", "sdpMid": "0", "sdpMLineIndex": 0}
    )

    await _unsubscribe(client, subscription_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    relay.close.assert_awaited_once()
    assert _state(hass) == CameraState.IDLE

    # a candidate arriving after teardown is ignored
    await _send_candidate(client, session_id, {"candidate": "candidate:3"})
    assert relay.send_candidate.await_count == 2


@pytest.mark.usefixtures("camera_client")
async def test_started_session_replaces_the_cached_credentials(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The next viewer reuses the credentials of the session that started."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)

    relay = _relay()
    relay.start.return_value = _session(
        turnCredentials=[{"urls": ["turn:started.example.com"]}]
    )
    with patch(RELAY, return_value=relay):
        await _send_offer(client)

    (server,) = await _ice_servers(client)
    assert server["urls"] == ["turn:started.example.com"]


@pytest.mark.parametrize("error", NETWORK_ERRORS)
@pytest.mark.usefixtures("camera_client")
async def test_webrtc_offer_failure(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    hass_ws_client: WebSocketGenerator,
    error: Exception,
) -> None:
    """A relay that fails to start reports why, and is closed and not kept."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)

    relay = _relay()
    relay.start.side_effect = error
    with patch(RELAY, return_value=relay):
        subscription_id, session_id = await _send_offer(client)

    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["event"] == {
        "type": "error",
        "code": "webrtc_offer_failed",
        "message": "Failed to start the camera stream: refused",
    }
    assert _state(hass) == CameraState.IDLE
    relay.close.assert_awaited_once()

    await _send_candidate(client, session_id, {"candidate": "candidate:1"})
    relay.send_candidate.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "reported"),
    [(ValueError("bad response"), True), (asyncio.CancelledError, False)],
)
@pytest.mark.usefixtures("camera_client")
async def test_relay_is_closed_when_start_fails_unexpectedly(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    hass_ws_client: WebSocketGenerator,
    error: BaseException,
    reported: bool,
) -> None:
    """An error the library does not wrap, or a cancel, must not leak the relay."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)

    relay = _relay()
    relay.start.side_effect = error
    with patch(RELAY, return_value=relay):
        subscription_id, session_id = await _send_offer(client)
    await hass.async_block_till_done(wait_background_tasks=True)
    if reported:
        # an unexpected error still reaches the frontend, through the
        # websocket's own error handling
        response = await client.receive_json()
        assert response["id"] == subscription_id
        assert response["success"] is False

    # start() may have left its signaling socket open
    relay.close.assert_awaited_once()
    await _send_candidate(client, session_id, {"candidate": "candidate:1"})
    relay.send_candidate.assert_not_awaited()


async def test_webrtc_offer_without_a_camera_client(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    camera_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A robot that can no longer provide a camera client reports it."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)
    mock_account_with_litterrobot_5_pro.robots[0].get_camera_client = MagicMock(
        side_effect=CameraNotAvailableException("no camera")
    )

    subscription_id, _ = await _send_offer(client)

    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["event"] == {
        "type": "error",
        "code": "webrtc_offer_failed",
        "message": "Camera is not available for this device: no camera",
    }


@pytest.mark.usefixtures("camera_client")
async def test_viewer_leaving_during_the_offer_does_not_leak_the_relay(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A session closed while start() connects must not be left running."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)
    connected = asyncio.Event()

    async def start(offer_sdp, on_answer, on_candidate):
        await connected.wait()
        return _session(turnCredentials=[{"urls": ["turn:late.example.com"]}])

    relay = _relay(start)
    with patch(RELAY, return_value=relay):
        subscription_id, _ = await _send_offer(client)
        # the browser closes the dialog while the relay is still connecting
        await _unsubscribe(client, subscription_id)
        connected.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    # closed by the teardown, and again once start() returned, so its socket
    # and tasks are not left running with no owner
    assert relay.close.await_count == 2
    assert _state(hass) == CameraState.IDLE
    # the abandoned session's credentials are not cached
    (server,) = await _ice_servers(client)
    assert server["urls"] == [TURN_URL]


@pytest.mark.usefixtures("camera_client")
async def test_viewer_leaving_before_a_failed_start_is_not_an_error(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A start that fails because the viewer already left logs no error."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)
    connected = asyncio.Event()
    failed = asyncio.Event()

    async def start(offer_sdp, on_answer, on_candidate):
        await connected.wait()
        failed.set()
        # the teardown closed the socket under start()
        raise ClientError("connection reset")

    relay = _relay(start)
    with patch(RELAY, return_value=relay):
        subscription_id, session_id = await _send_offer(client)
        await _unsubscribe(client, subscription_id)
        connected.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert failed.is_set()
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    # closed by the teardown, and again once start() failed
    assert relay.close.await_count == 2
    # nothing else was sent for the offer: the next message answers this
    await _send_candidate(client, session_id, {"candidate": "candidate:1"})


@pytest.mark.usefixtures("camera_client")
async def test_streaming_follows_started_sessions(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The camera streams while any viewer is connected, not a pending offer."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)

    with patch(RELAY, side_effect=[_relay(), _relay()]):
        first, _ = await _send_offer(client)
        second, _ = await _send_offer(client)
    assert _state(hass) == CameraState.STREAMING

    # one viewer leaving does not stop the other's stream
    await _unsubscribe(client, first)
    assert _state(hass) == CameraState.STREAMING
    await _unsubscribe(client, second)
    assert _state(hass) == CameraState.IDLE

    # a viewer still negotiating does not count as streaming, and its
    # failure leaves the camera idle
    fail = asyncio.Event()

    async def start(offer_sdp, on_answer, on_candidate):
        await fail.wait()
        raise CameraStreamException("refused")

    with patch(RELAY, side_effect=[_relay(), _relay(start)]):
        third, _ = await _send_offer(client)
        await _send_offer(client)
        await _unsubscribe(client, third)
        assert _state(hass) == CameraState.IDLE
        fail.set()
        await hass.async_block_till_done(wait_background_tasks=True)
    assert _state(hass) == CameraState.IDLE


@pytest.mark.parametrize("error", NETWORK_ERRORS)
async def test_failed_session_fetch_is_retried_on_the_next_request(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    camera_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
    error: Exception,
) -> None:
    """A failed fetch only costs the TURN servers until the next request."""
    camera_client.generate_session.side_effect = error
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)
    assert _state(hass) == CameraState.IDLE

    camera_client.generate_session.side_effect = None
    # this request finds nothing usable and fetches for the next one
    assert await _ice_servers(client) == []
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(await _ice_servers(client)) == 1


async def test_expired_session_is_not_served(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    camera_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Expired TURN credentials are withheld and replaced, not served."""
    camera_client.generate_session.return_value = _session(
        sessionExpiration="2020-01-01T00:00:00.000000Z"
    )
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)

    camera_client.generate_session.return_value = _session()
    assert await _ice_servers(client) == []
    await hass.async_block_till_done(wait_background_tasks=True)
    assert camera_client.generate_session.await_count == 2
    assert len(await _ice_servers(client)) == 1


async def test_concurrent_requests_fetch_one_session(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    camera_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Requests arriving while a fetch is running do not start another."""
    camera_client.generate_session.side_effect = CameraStreamException("down")
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)
    release = asyncio.Event()

    async def slow_session(auto_start: bool) -> CameraSession:
        await release.wait()
        return _session()

    camera_client.generate_session.reset_mock()
    camera_client.generate_session.side_effect = slow_session
    for _ in range(3):
        assert await _ice_servers(client) == []
    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert camera_client.generate_session.await_count == 1


async def test_session_is_not_renewed_in_the_background(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    camera_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An idle camera must not keep creating sessions.

    Guards against reintroducing a renewal timer. Sessions are short-lived, so
    renewing one ahead of its expiry would create a new camera session every
    few minutes, whether or not anyone is watching.
    """
    # expires inside the interval advanced below, so a renewal scheduled
    # before expiry, or after it, would fire
    camera_client.generate_session.return_value = _session(
        sessionExpiration=_expiring_in(60)
    )
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    fetched = camera_client.generate_session.await_count

    freezer.tick(timedelta(hours=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert camera_client.generate_session.await_count == fetched


async def test_camera_added_for_a_robot_discovered_after_setup(
    hass: HomeAssistant,
    mock_account_with_no_robots: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A camera robot that appears after setup gets its entity without a reload."""
    await setup_integration(hass, mock_account_with_no_robots, CAMERA_DOMAIN)
    assert hass.states.get(CAMERA_ENTITY_ID) is None

    robot = create_mock_robot(
        None,
        mock_account_with_no_robots,
        v4=False,
        v5=False,
        v5_pro=True,
        feeder=False,
    )
    robot.get_camera_client().generate_session = AsyncMock(return_value=_session())
    mock_account_with_no_robots.robots.append(robot)

    freezer.tick(timedelta(seconds=305))  # the coordinator's 5 minute refresh
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(CAMERA_ENTITY_ID) is not None

    # a later refresh must not add it a second time
    freezer.tick(timedelta(seconds=305))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(hass.states.async_entity_ids(CAMERA_DOMAIN)) == 1


@pytest.mark.usefixtures("camera_client")
async def test_unload_waits_for_live_relays_to_close(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Unloading closes live streams before it returns."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)
    release = asyncio.Event()
    relay = _relay()
    relay.close.side_effect = release.wait
    with patch(RELAY, return_value=relay):
        await _send_offer(client)

    (entry,) = hass.config_entries.async_entries("litterrobot")
    unload = hass.async_create_task(hass.config_entries.async_unload(entry.entry_id))
    for _ in range(5):
        await asyncio.sleep(0)
    assert not unload.done()

    release.set()
    assert await unload
    assert entry.state is ConfigEntryState.NOT_LOADED
    relay.close.assert_awaited_once()


@pytest.mark.usefixtures("camera_client")
async def test_unload_waits_for_a_pending_relay_close(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A close still running when the entry unloads is awaited, not abandoned."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)
    release = asyncio.Event()
    relay = _relay()
    relay.close.side_effect = release.wait
    with patch(RELAY, return_value=relay):
        subscription_id, _ = await _send_offer(client)

    # the viewer leaves, and the entry unloads before the close has finished
    await _unsubscribe(client, subscription_id)
    (entry,) = hass.config_entries.async_entries("litterrobot")
    unload = hass.async_create_task(hass.config_entries.async_unload(entry.entry_id))
    for _ in range(5):
        await asyncio.sleep(0)
    assert not unload.done()

    release.set()
    assert await unload


@pytest.mark.usefixtures("camera_client")
async def test_unload_closes_every_relay_when_one_fails(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One relay failing to close does not leave the others open."""
    await _setup(hass, mock_account_with_litterrobot_5_pro)
    client = await hass_ws_client(hass)
    failing, healthy = _relay(), _relay()
    failing.close.side_effect = ClientError("already gone")
    with patch(RELAY, side_effect=[failing, healthy]):
        await _send_offer(client)
        await _send_offer(client)

    (entry,) = hass.config_entries.async_entries("litterrobot")
    assert await hass.config_entries.async_unload(entry.entry_id)

    healthy.close.assert_awaited_once()
    assert "Error closing WebRTC session" in caplog.text


def test_ice_servers_standard_format() -> None:
    """The documented format maps straight through."""
    (server,) = _build_ice_servers(_session())
    assert server.urls == [TURN_URL]
    assert server.username == "turn-user"
    assert server.credential == "turn-pass"


def test_ice_servers_uris_key_and_string_url() -> None:
    """A bare "uris" string is accepted and wrapped into a list."""
    (server,) = _build_ice_servers(
        _session(turnCredentials=[{"uris": "turn:turn.example.com:443"}])
    )
    assert server.urls == ["turn:turn.example.com:443"]
    # absent credentials become empty strings rather than None
    assert server.username == ""
    assert server.credential == ""


def test_ice_servers_watford_format() -> None:
    """The Watford variant supplies turnUrl/stunUrl and "password"."""
    (server,) = _build_ice_servers(
        _session(
            turnCredentials=[
                {
                    "turnUrl": ["turn:turn.example.com:443"],
                    "stunUrl": "stun:stun.example.com:3478",
                    "username": "turn-user",
                    "password": "turn-pass",
                }
            ]
        )
    )
    assert server.urls == ["turn:turn.example.com:443", "stun:stun.example.com:3478"]
    assert server.credential == "turn-pass"


def test_ice_servers_turn_url_as_a_string() -> None:
    """A bare turnUrl string is wrapped, and the stun url follows it."""
    (server,) = _build_ice_servers(
        _session(
            turnCredentials=[
                {
                    "turnUrl": "turn:turn.example.com:443",
                    "stunUrl": "stun:stun.example.com:3478",
                }
            ]
        )
    )
    assert server.urls == ["turn:turn.example.com:443", "stun:stun.example.com:3478"]


def test_ice_servers_empty_urls_fall_back_to_turn_url() -> None:
    """An empty "urls" list does not hide the Watford fields."""
    (server,) = _build_ice_servers(
        _session(
            turnCredentials=[{"urls": [], "turnUrl": ["turn:turn.example.com:443"]}]
        )
    )
    assert server.urls == ["turn:turn.example.com:443"]


def test_ice_servers_multiple_credentials() -> None:
    """Every credential with a url becomes its own server."""
    servers = _build_ice_servers(
        _session(
            turnCredentials=[
                {"urls": ["turn:a.example.com"], "username": "a", "credential": "x"},
                {"username": "no-url"},
                {"urls": ["turn:b.example.com"], "username": "b", "credential": "y"},
            ]
        )
    )
    assert [server.username for server in servers] == ["a", "b"]


def test_ice_servers_does_not_mutate_session() -> None:
    """Sessions are cached and reused, so building must not append in place."""
    session = _session(
        turnCredentials=[
            {
                "turnUrl": ["turn:turn.example.com:443"],
                "stunUrl": "stun:stun.example.com:3478",
            }
        ]
    )
    # copy: both calls would otherwise hand back the same mutated list object
    # and compare equal to itself
    first = list(_build_ice_servers(session)[0].urls)
    second = list(_build_ice_servers(session)[0].urls)
    assert first == second
    assert session.turn_servers[0]["turnUrl"] == ["turn:turn.example.com:443"]


def test_ice_servers_skips_entries_without_urls() -> None:
    """A credential carrying no usable url contributes no server."""
    assert _build_ice_servers(_session(turnCredentials=[{"username": "u"}])) == []
