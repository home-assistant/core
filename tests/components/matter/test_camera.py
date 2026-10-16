"""Test Matter cameras."""

import asyncio
import base64
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, call, patch

from matter_server.client.models.node import MatterNode
from matter_server.common.errors import CameraNotSupported, MatterError
from matter_server.common.models import (
    CameraResolution,
    CameraSessionEndedData,
    CameraSnapshotResult,
    CameraStartStreamResult,
    CameraStopStreamResult,
    CameraStreamEvictedData,
    EventType,
)
import pytest
from syrupy.assertion import SnapshotAssertion
from webrtc_models import RTCIceServer

from homeassistant.components.camera import (
    CameraState,
    StreamType,
    async_get_image,
    get_camera_from_entity_id,
)
from homeassistant.components.matter import DOMAIN
from homeassistant.components.web_rtc import async_register_ice_servers
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
DEFAULT_ICE_SERVERS = [
    {
        "urls": [
            "stun:stun.home-assistant.io:3478",
            "stun:stun.home-assistant.io:80",
        ]
    }
]


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


async def _start_session(
    client: MockHAClientWebSocket,
    matter_client: MagicMock,
) -> tuple[int, str]:
    """Send an offer and return the WS subscription id and the HA session id."""
    matter_client.camera_start_stream.return_value = CameraStartStreamResult(
        webrtc_session_id=MATTER_SESSION_ID,
        mode="provide_offer",
        video=None,
        audio=None,
    )
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
    session_id = response["event"]["session_id"]
    return subscription_id, session_id


@pytest.mark.usefixtures("matter_devices")
async def test_cameras(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test cameras."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.CAMERA)


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_capabilities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that the camera advertises native WebRTC support only."""
    camera = get_camera_from_entity_id(hass, ENTITY_ID)
    assert camera.camera_capabilities.frontend_stream_types == {StreamType.WEB_RTC}


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

    # camera_start_stream is called with the frontend offer; the server
    # allocates whatever streams it needs, so no hints are sent.
    assert matter_client.camera_start_stream.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        stream_usage="LiveView",
        sdp="v=0\r\n",
        ice_servers=DEFAULT_ICE_SERVERS,
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
    assert (
        matter_client.camera_provide_ice_candidates.call_args.kwargs["node_id"]
        == matter_node.node_id
    )
    assert (
        matter_client.camera_provide_ice_candidates.call_args.kwargs[
            "webrtc_session_id"
        ]
        == MATTER_SESSION_ID
    )
    [ice_candidate] = matter_client.camera_provide_ice_candidates.call_args.kwargs[
        "ice_candidates"
    ]
    assert ice_candidate.candidate == "c2"
    assert ice_candidate.sdpMLineIndex == 1

    # Closing the session ends it on the camera.
    matter_client.camera_stop_stream.return_value = CameraStopStreamResult(ended=True)
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": subscription_id,
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        webrtc_session_id=MATTER_SESSION_ID,
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_ice_servers_with_credentials(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that an ICE server's username/credential are forwarded when set."""
    async_register_ice_servers(
        hass,
        lambda: [
            RTCIceServer(
                urls="turn:turn.example.com:3478",
                username="user",
                credential="pass",
            )
        ],
    )
    client = await hass_ws_client(hass)
    await _start_session(client, matter_client)

    ice_servers = matter_client.camera_start_stream.call_args.kwargs["ice_servers"]
    assert ice_servers[-1] == {
        "urls": "turn:turn.example.com:3478",
        "username": "user",
        "credential": "pass",
    }


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_candidate_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a camera_provide_ice_candidates failure surfaces to the frontend."""
    client = await hass_ws_client(hass)
    _, session_id = await _start_session(client, matter_client)

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


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_end_event(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that an 'end' event cleans up so close does not send camera_stop_stream."""
    client = await hass_ws_client(hass)
    subscription_id, _ = await _start_session(client, matter_client)

    # The device ends the session.
    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.WEBRTC_CALLBACK,
        data=_webrtc_callback_data(matter_node, "end", {"reason": 11}),
    )

    matter_client.camera_stop_stream.reset_mock()
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": subscription_id,
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_count == 0


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_callback_unknown_session(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that a WEBRTC_CALLBACK event for an unknown session is ignored."""
    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.WEBRTC_CALLBACK,
        data=_webrtc_callback_data(matter_node, "answer", {"sdp": "orphan"}),
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_candidate_before_offer_resolves(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a frontend candidate that arrives while the offer is in flight."""
    release = asyncio.Event()

    async def blocked_offer(**kwargs: Any) -> CameraStartStreamResult:
        await release.wait()
        return CameraStartStreamResult(
            webrtc_session_id=MATTER_SESSION_ID,
            mode="provide_offer",
            video=None,
            audio=None,
        )

    matter_client.camera_start_stream.side_effect = blocked_offer
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": ENTITY_ID,
            "offer": "v=0\r\n",
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    response = await client.receive_json()
    assert response["event"]["type"] == "session"
    session_id = response["event"]["session_id"]

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
    assert (
        matter_client.camera_provide_ice_candidates.call_args.kwargs[
            "webrtc_session_id"
        ]
        == MATTER_SESSION_ID
    )
    [ice_candidate] = matter_client.camera_provide_ice_candidates.call_args.kwargs[
        "ice_candidates"
    ]
    assert ice_candidate.candidate == "c1"


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_offer_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a failing offer cleans up the session."""
    matter_client.camera_start_stream.side_effect = CameraNotSupported(
        '{"missing_clusters": [1363]}'
    )
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": ENTITY_ID,
            "offer": "v=0\r\n",
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    response = await client.receive_json()
    assert response["event"]["type"] == "session"
    session_id = response["event"]["session_id"]

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


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_session_ended_event(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a camera_session_ended event cleans up without sending camera_stop_stream."""
    client = await hass_ws_client(hass)
    subscription_id, _ = await _start_session(client, matter_client)

    # Another connection ended the session on the camera.
    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.CAMERA_SESSION_ENDED,
        data=CameraSessionEndedData(
            node_id=matter_node.node_id,
            endpoint_id=1,
            webrtc_session_id=MATTER_SESSION_ID,
        ),
    )

    matter_client.camera_stop_stream.reset_mock()
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": subscription_id,
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_count == 0


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_session_ended_event_other_endpoint(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a camera_session_ended event for another endpoint is ignored."""
    client = await hass_ws_client(hass)
    subscription_id, _ = await _start_session(client, matter_client)

    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.CAMERA_SESSION_ENDED,
        data=CameraSessionEndedData(
            node_id=matter_node.node_id,
            endpoint_id=2,
            webrtc_session_id=MATTER_SESSION_ID,
        ),
    )

    matter_client.camera_stop_stream.return_value = CameraStopStreamResult(ended=True)
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": subscription_id,
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_count == 1


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_stream_evicted_event(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that a camera_stream_evicted event does not raise."""
    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.CAMERA_STREAM_EVICTED,
        data=CameraStreamEvictedData(
            node_id=matter_node.node_id,
            endpoint_id=1,
            kind="video",
            stream_id=1,
        ),
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_stream_evicted_event_other_endpoint(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that a camera_stream_evicted event for another endpoint is ignored."""
    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.CAMERA_STREAM_EVICTED,
        data=CameraStreamEvictedData(
            node_id=matter_node.node_id,
            endpoint_id=2,
            kind="video",
            stream_id=1,
        ),
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_close_session_before_offer_resolves(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test closing a session whose offer hasn't resolved yet sends no camera_stop_stream."""
    release = asyncio.Event()

    async def blocked_offer(**kwargs: Any) -> CameraStartStreamResult:
        await release.wait()
        return CameraStartStreamResult(
            webrtc_session_id=MATTER_SESSION_ID,
            mode="provide_offer",
            video=None,
            audio=None,
        )

    matter_client.camera_start_stream.side_effect = blocked_offer
    client = await hass_ws_client(hass)

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

    # Close the session while the offer is still in flight.
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": subscription_id,
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    assert matter_client.camera_stop_stream.call_count == 0

    # Let the blocked offer finish so no task is left dangling.
    release.set()
    await hass.async_block_till_done()


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_close_session_stop_stream_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a camera_stop_stream failure on close is logged, not raised."""
    client = await hass_ws_client(hass)
    subscription_id, _ = await _start_session(client, matter_client)

    matter_client.camera_stop_stream.side_effect = MatterError("boom")
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": subscription_id,
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    await hass.async_block_till_done()


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_removal_closes_sessions(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that removing the entity closes any open WebRTC session."""
    client = await hass_ws_client(hass)
    await _start_session(client, matter_client)

    matter_client.camera_stop_stream.return_value = CameraStopStreamResult(ended=True)
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
    """Test that the camera returns a real snapshot and releases the stream."""
    image_bytes = b"fake-jpeg-bytes"
    matter_client.camera_snapshot.return_value = CameraSnapshotResult(
        data=base64.b64encode(image_bytes).decode(),
        codec="JPEG",
        resolution=CameraResolution(width=640, height=480),
        degraded=False,
        stream_id=9,
        provenance="allocated",
    )
    image = await async_get_image(hass, ENTITY_ID)
    assert image.content == image_bytes
    assert matter_client.camera_snapshot.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
    )
    await hass.async_block_till_done()
    assert matter_client.camera_release_stream.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        kind="snapshot",
        stream_id=9,
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_image_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that a camera_snapshot failure surfaces as a HomeAssistantError."""
    matter_client.camera_snapshot.side_effect = MatterError("boom")
    with pytest.raises(HomeAssistantError, match="boom"):
        await async_get_image(hass, ENTITY_ID)


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_image_release_stream_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that a camera_release_stream failure after a snapshot is logged, not raised."""
    image_bytes = b"fake-jpeg-bytes"
    matter_client.camera_snapshot.return_value = CameraSnapshotResult(
        data=base64.b64encode(image_bytes).decode(),
        codec="JPEG",
        resolution=CameraResolution(width=640, height=480),
        degraded=False,
        stream_id=9,
        provenance="allocated",
    )
    matter_client.camera_release_stream.side_effect = MatterError("boom")

    image = await async_get_image(hass, ENTITY_ID)
    assert image.content == image_bytes
    await hass.async_block_till_done()
