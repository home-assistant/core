"""Test Matter cameras."""

import asyncio
from base64 import b64encode
from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import MagicMock, call, patch

from matter_server.client.models.node import MatterNode
from matter_server.common.errors import CameraPrivacyMode, MatterError
from matter_server.common.models import (
    CameraResolution,
    CameraSessionEndedData,
    CameraSnapshotResult,
    CameraStartStreamResult,
    EventType,
    WebRTCIceCandidate,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import (
    CameraState,
    StreamType,
    async_get_image,
    get_camera_from_entity_id,
)
from homeassistant.components.matter.camera import CAMERA_SCHEMA_VERSION
from homeassistant.components.matter.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)

from tests.typing import MockHAClientWebSocket, WebSocketGenerator

ENTITY_ID = "camera.mock_camera"
MATTER_SESSION_ID = 5
CURRENT_SESSION = {
    "0": MATTER_SESSION_ID,
    "1": 1,
    "2": 1,
    "3": 3,
    "4": 1,
    "5": 1,
    "6": False,
    "254": 1,
}
START_STREAM_RESULT = CameraStartStreamResult(
    webrtc_session_id=MATTER_SESSION_ID,
    mode="provide_offer",
    video=None,
    audio=None,
)
SECOND_START_STREAM_RESULT = CameraStartStreamResult(
    webrtc_session_id=MATTER_SESSION_ID + 1,
    mode="provide_offer",
    video=None,
    audio=None,
)
SNAPSHOT_IMAGE = b"\xff\xd8snapshot"


@pytest.fixture
def server_schema_version() -> int:
    """Return the schema version reported by the mocked Matter server."""
    return CAMERA_SCHEMA_VERSION


@pytest.fixture(autouse=True)
async def mock_server_schema(
    matter_client: MagicMock, server_schema_version: int
) -> None:
    """Report a Matter server schema version to the integration."""
    matter_client.server_info.schema_version = server_schema_version


@pytest.fixture(autouse=True)
def mock_getrandbits() -> Generator[None]:
    """Mock camera access token which is normally randomized."""
    with patch(
        "homeassistant.components.camera.entity.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


def _webrtc_callback_data(
    matter_node: MatterNode,
    event_type: str,
    data: dict[str, Any],
    *,
    endpoint_id: int = 1,
    session_id: int = MATTER_SESSION_ID,
) -> dict[str, Any]:
    """Build a raw WEBRTC_CALLBACK event payload."""
    return {
        "event_type": event_type,
        "webrtc_session_id": session_id,
        "node_id": matter_node.node_id,
        "endpoint_id": endpoint_id,
        "fabric_index": 1,
        "data": data,
    }


def _get_webrtc_callback(matter_client: MagicMock) -> Callable[[EventType, Any], None]:
    """Return the entity's WEBRTC_CALLBACK subscription callback."""
    for sub in matter_client.subscribe_events.call_args_list:
        if sub.kwargs.get("event_filter") == EventType.WEBRTC_CALLBACK:
            return sub.kwargs["callback"]
    raise AssertionError("No WEBRTC_CALLBACK subscription found")


async def _send_offer(client: MockHAClientWebSocket) -> tuple[int, str]:
    """Send an offer and return the WS subscription id and the HA session id."""
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": ENTITY_ID,
            "offer": "v=0\r\n",
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    subscription_id = response["id"]

    response = await client.receive_json()
    assert response["event"]["type"] == "session"
    return subscription_id, response["event"]["session_id"]


async def _start_session(
    client: MockHAClientWebSocket,
    matter_client: MagicMock,
) -> tuple[int, str]:
    """Start a session with a successful camera_start_stream."""
    matter_client.camera_start_stream.return_value = START_STREAM_RESULT
    return await _send_offer(client)


async def _unsubscribe(client: MockHAClientWebSocket, subscription_id: int) -> None:
    """Close the frontend session."""
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": subscription_id,
        }
    )
    response = await client.receive_json()
    assert response["success"] is True


@pytest.mark.usefixtures("matter_devices")
async def test_cameras(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test cameras."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.CAMERA)


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.usefixtures("matter_node")
async def test_camera_capabilities(hass: HomeAssistant) -> None:
    """Test that the camera advertises native WebRTC support."""
    camera = get_camera_from_entity_id(hass, ENTITY_ID)
    assert camera.camera_capabilities.frontend_stream_types == {StreamType.WEB_RTC}


@pytest.mark.parametrize("server_schema_version", [CAMERA_SCHEMA_VERSION - 1])
@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.usefixtures("matter_node")
async def test_camera_requires_server_schema(hass: HomeAssistant) -> None:
    """Test that no camera is created for a server without the camera API."""
    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the full WebRTC offer/answer/candidate/close flow."""
    client = await hass_ws_client(hass)
    subscription_id, session_id = await _start_session(client, matter_client)

    # The frontend offer starts a live view stream on the camera.
    assert matter_client.camera_start_stream.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        stream_usage="LiveView",
        sdp="v=0\r\n",
        ice_servers=[
            {
                "urls": [
                    "stun:stun.home-assistant.io:3478",
                    "stun:stun.home-assistant.io:80",
                ]
            }
        ],
    )

    # The camera answer is relayed to the frontend.
    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.WEBRTC_CALLBACK,
        data=_webrtc_callback_data(matter_node, "answer", {"sdp": "v=0\r\nanswer"}),
    )
    response = await client.receive_json()
    assert response["event"] == {"type": "answer", "answer": "v=0\r\nanswer"}

    # Camera ICE candidates are relayed to the frontend.
    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.WEBRTC_CALLBACK,
        data=_webrtc_callback_data(
            matter_node,
            "ice_candidates",
            {
                "ice_candidates": [
                    {"candidate": "c1", "sdpMid": "0", "sdpMLineIndex": 0}
                ]
            },
        ),
    )
    response = await client.receive_json()
    assert response["event"]["type"] == "candidate"
    assert response["event"]["candidate"]["candidate"] == "c1"

    # An event for a different endpoint is ignored (no WS event emitted).
    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.WEBRTC_CALLBACK,
        data=_webrtc_callback_data(
            matter_node, "answer", {"sdp": "other"}, endpoint_id=2
        ),
    )

    # A frontend candidate is forwarded to the camera.
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": ENTITY_ID,
            "session_id": session_id,
            "candidate": {"candidate": "c2", "sdpMLineIndex": 1},
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    assert matter_client.camera_provide_ice_candidates.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        webrtc_session_id=MATTER_SESSION_ID,
        ice_candidates=[WebRTCIceCandidate("c2", sdpMid=None, sdpMLineIndex=1)],
    )

    # Closing the session ends it on the camera.
    await _unsubscribe(client, subscription_id)
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        webrtc_session_id=MATTER_SESSION_ID,
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_candidate_before_answer(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a frontend candidate that arrives while the offer is in flight."""
    release = asyncio.Event()

    async def blocked_offer(**kwargs: Any) -> CameraStartStreamResult:
        await release.wait()
        return START_STREAM_RESULT

    matter_client.camera_start_stream.side_effect = blocked_offer
    client = await hass_ws_client(hass)
    _, session_id = await _send_offer(client)

    # Candidate arrives while camera_start_stream is still blocked -> buffered.
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": ENTITY_ID,
            "session_id": session_id,
            "candidate": {"candidate": "c1", "sdpMLineIndex": 0},
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    assert matter_client.camera_provide_ice_candidates.call_count == 0

    # Releasing the offer flushes the buffered candidate.
    release.set()
    await hass.async_block_till_done()
    assert matter_client.camera_provide_ice_candidates.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        webrtc_session_id=MATTER_SESSION_ID,
        ice_candidates=[WebRTCIceCandidate("c1", sdpMid=None, sdpMLineIndex=0)],
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_answer_races_offer(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test an answer event dispatched before the camera_start_stream result."""

    async def racing_offer(**kwargs: Any) -> CameraStartStreamResult:
        # The device answer is dispatched before the session id is known.
        callback = _get_webrtc_callback(matter_client)
        callback(
            EventType.WEBRTC_CALLBACK,
            _webrtc_callback_data(matter_node, "answer", {"sdp": "raced"}),
        )
        return START_STREAM_RESULT

    matter_client.camera_start_stream.side_effect = racing_offer
    client = await hass_ws_client(hass)
    await _send_offer(client)

    # The buffered answer is relayed once the offer completes.
    response = await client.receive_json()
    assert response["event"] == {"type": "answer", "answer": "raced"}


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_end_races_offer(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test buffered events that follow a buffered end are dropped."""

    async def racing_offer(**kwargs: Any) -> CameraStartStreamResult:
        callback = _get_webrtc_callback(matter_client)
        callback(
            EventType.WEBRTC_CALLBACK,
            _webrtc_callback_data(matter_node, "end", {"reason": 11}),
        )
        callback(
            EventType.WEBRTC_CALLBACK,
            _webrtc_callback_data(matter_node, "answer", {"sdp": "late"}),
        )
        return START_STREAM_RESULT

    matter_client.camera_start_stream.side_effect = racing_offer
    client = await hass_ws_client(hass)
    subscription_id, _ = await _send_offer(client)

    # The session ended before it was established, so closing sends nothing.
    await _unsubscribe(client, subscription_id)
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_count == 0


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_closed_during_offer(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a session closed by the frontend while the offer is in flight."""
    release = asyncio.Event()

    async def blocked_offer(**kwargs: Any) -> CameraStartStreamResult:
        await release.wait()
        return START_STREAM_RESULT

    matter_client.camera_start_stream.side_effect = blocked_offer
    client = await hass_ws_client(hass)
    subscription_id, _ = await _send_offer(client)

    await _unsubscribe(client, subscription_id)
    assert matter_client.camera_stop_stream.call_count == 0

    # The camera session created by the late result is stopped right away.
    release.set()
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        webrtc_session_id=MATTER_SESSION_ID,
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_concurrent_offers(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test two offers in flight at once each get their own early events."""
    release = asyncio.Event()
    results = iter([START_STREAM_RESULT, SECOND_START_STREAM_RESULT])

    async def blocked_offer(**kwargs: Any) -> CameraStartStreamResult:
        await release.wait()
        return next(results)

    matter_client.camera_start_stream.side_effect = blocked_offer
    client = await hass_ws_client(hass)
    first_subscription_id, _ = await _send_offer(client)
    second_subscription_id, _ = await _send_offer(client)

    # Both answers arrive while both offers are still in flight.
    for session_id, sdp in (
        (MATTER_SESSION_ID, "first"),
        (MATTER_SESSION_ID + 1, "second"),
    ):
        await trigger_subscription_callback(
            hass,
            matter_client,
            event=EventType.WEBRTC_CALLBACK,
            data=_webrtc_callback_data(
                matter_node, "answer", {"sdp": sdp}, session_id=session_id
            ),
        )

    release.set()
    await hass.async_block_till_done()
    answers = {}
    for _ in range(2):
        response = await client.receive_json()
        answers[response["id"]] = response["event"]["answer"]
    assert answers == {first_subscription_id: "first", second_subscription_id: "second"}


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_session_id_reuse(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a stale session is dropped when the camera reuses its session id."""
    client = await hass_ws_client(hass)
    stale_subscription_id, _ = await _start_session(client, matter_client)
    # The camera restarted and the stale session's end was never seen.
    new_subscription_id, _ = await _start_session(client, matter_client)

    # Closing the stale session must not end the new one on the camera.
    await _unsubscribe(client, stale_subscription_id)
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_count == 0

    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.WEBRTC_CALLBACK,
        data=_webrtc_callback_data(matter_node, "answer", {"sdp": "new"}),
    )
    response = await client.receive_json()
    assert response["id"] == new_subscription_id
    assert response["event"] == {"type": "answer", "answer": "new"}

    await _unsubscribe(client, new_subscription_id)
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_count == 1


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.usefixtures("matter_node")
async def test_camera_webrtc_offer_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a failing offer cleans up the session."""
    matter_client.camera_start_stream.side_effect = CameraPrivacyMode()
    client = await hass_ws_client(hass)
    _, session_id = await _send_offer(client)

    response = await client.receive_json()
    assert response["event"]["type"] == "error"
    assert response["event"]["code"] == "webrtc_offer_failed"

    # The session was cleaned up, so a later candidate fails.
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": ENTITY_ID,
            "session_id": session_id,
            "candidate": {"candidate": "c1", "sdpMLineIndex": 0},
        }
    )
    response = await client.receive_json()
    assert response["success"] is False


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.usefixtures("matter_node")
async def test_camera_webrtc_command_errors(
    hass: HomeAssistant,
    matter_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test errors from forwarding a candidate and from stopping a session."""
    client = await hass_ws_client(hass)
    subscription_id, session_id = await _start_session(client, matter_client)

    matter_client.camera_provide_ice_candidates.side_effect = MatterError("boom")
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": ENTITY_ID,
            "session_id": session_id,
            "candidate": {"candidate": "c1", "sdpMLineIndex": 0},
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["message"] == "boom"

    # A failing stop is only logged.
    matter_client.camera_stop_stream.side_effect = MatterError("stop failed")
    await _unsubscribe(client, subscription_id)
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_count == 1
    assert "Error stopping WebRTC session 5: stop failed" in caplog.text


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_states(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test camera state and privacy handling."""
    camera = get_camera_from_entity_id(hass, ENTITY_ID)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == CameraState.IDLE
    assert camera.is_on is True

    # An active session reports streaming.
    set_node_attribute(matter_node, 1, 1363, 0, [CURRENT_SESSION])
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == CameraState.STREAMING

    # Soft privacy mode turns the camera off.
    set_node_attribute(matter_node, 1, 1361, 20, True)
    await trigger_subscription_callback(hass, matter_client)
    assert camera.is_on is False

    set_node_attribute(matter_node, 1, 1361, 20, False)
    set_node_attribute(matter_node, 1, 1361, 21, True)
    await trigger_subscription_callback(hass, matter_client)
    assert camera.is_on is False


@pytest.mark.parametrize(
    ("event", "data"),
    [
        pytest.param(
            EventType.WEBRTC_CALLBACK,
            {
                "event_type": "end",
                "webrtc_session_id": MATTER_SESSION_ID,
                "node_id": 365,
                "endpoint_id": 1,
                "fabric_index": 1,
                "data": {"reason": 11},
            },
            id="device_end",
        ),
        pytest.param(
            EventType.CAMERA_SESSION_ENDED,
            CameraSessionEndedData(
                node_id=365, endpoint_id=1, webrtc_session_id=MATTER_SESSION_ID
            ),
            id="server_session_ended",
        ),
    ],
)
@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.usefixtures("matter_node")
async def test_camera_session_ended_events(
    hass: HomeAssistant,
    matter_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
    event: EventType,
    data: Any,
) -> None:
    """Test that an ended session is forgotten so close does not stop it again."""
    client = await hass_ws_client(hass)
    subscription_id, _ = await _start_session(client, matter_client)

    await trigger_subscription_callback(hass, matter_client, event=event, data=data)

    await _unsubscribe(client, subscription_id)
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_count == 0


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_unload_closes_sessions(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that unloading the config entry ends open sessions on the camera."""
    client = await hass_ws_client(hass)
    await _start_session(client, matter_client)

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        webrtc_session_id=MATTER_SESSION_ID,
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_image(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test snapshots."""
    camera = get_camera_from_entity_id(hass, ENTITY_ID)
    matter_client.camera_snapshot.return_value = CameraSnapshotResult(
        data=b64encode(SNAPSHOT_IMAGE).decode(),
        codec="JPEG",
        resolution=CameraResolution(width=640, height=480),
        degraded=False,
        stream_id=1,
        provenance="allocated",
    )
    image = await async_get_image(hass, ENTITY_ID)
    assert image.content == SNAPSHOT_IMAGE
    assert image.content_type == "image/jpeg"
    assert matter_client.camera_snapshot.call_args == call(
        node_id=matter_node.node_id, endpoint_id=1
    )
    assert camera.content_type == "image/jpeg"

    matter_client.camera_snapshot.side_effect = MatterError("boom")
    with pytest.raises(HomeAssistantError, match="boom"):
        await async_get_image(hass, ENTITY_ID)
