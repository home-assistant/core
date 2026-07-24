"""Test Matter cameras."""

import asyncio
from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import MagicMock, call, patch

from chip.clusters import Objects as clusters
from chip.clusters.Objects import NullValue
from matter_server.client.models.node import MatterNode
from matter_server.common.errors import MatterError
from matter_server.common.models import EventType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import (
    CameraState,
    StreamType,
    async_get_image,
    get_camera_from_entity_id,
)
from homeassistant.components.matter.camera import PLACEHOLDER
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
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


@pytest.fixture(autouse=True)
def mock_getrandbits() -> Generator[None]:
    """Mock camera access token which is normally randomized."""
    with patch(
        "homeassistant.components.camera.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


def _webrtc_callback_data(
    matter_node: MatterNode,
    event_type: str,
    data: dict[str, Any],
    *,
    node_id: int | None = None,
    endpoint_id: int = 1,
    session_id: int = MATTER_SESSION_ID,
) -> dict[str, Any]:
    """Build a raw WEBRTC_CALLBACK event payload."""
    return {
        "event_type": event_type,
        "webrtc_session_id": session_id,
        "node_id": matter_node.node_id if node_id is None else node_id,
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


async def _start_session(
    client: MockHAClientWebSocket,
    matter_client: MagicMock,
) -> tuple[int, str]:
    """Send an offer and return the WS subscription id and the HA session id."""
    matter_client.send_webrtc_provider_command.return_value = {
        "webRtcSessionId": MATTER_SESSION_ID,
        "videoStreamId": 1,
        "audioStreamId": 1,
    }
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

    # ProvideOffer is sent to the camera with the frontend offer.
    assert matter_client.send_webrtc_provider_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command_name="ProvideOffer",
        payload={
            "webRtcSessionID": None,
            "sdp": "v=0\r\n",
            "streamUsage": clusters.Globals.Enums.StreamUsageEnum.kLiveView,
            "videoStreamID": None,
            "audioStreamID": None,
            "iceServers": [
                clusters.WebRtcTransportDefinitions.Structs.ICEServerStruct(
                    urLs=[
                        "stun:stun.home-assistant.io:3478",
                        "stun:stun.home-assistant.io:80",
                    ],
                )
            ],
        },
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
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.WebRtcTransportProvider.Commands.ProvideIceCandidates(
            webRtcSessionID=MATTER_SESSION_ID,
            iceCandidates=[
                clusters.WebRtcTransportDefinitions.Structs.ICECandidateStruct(
                    candidate="c2",
                    sdpMid=NullValue,
                    sdpmLineIndex=1,
                )
            ],
        ),
    )

    # Closing the session ends it on the camera.
    matter_client.send_device_command.reset_mock()
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": subscription_id,
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    await hass.async_block_till_done()
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.WebRtcTransportProvider.Commands.EndSession(
            webRtcSessionID=MATTER_SESSION_ID,
            reason=clusters.WebRtcTransportDefinitions.Enums.WebRTCEndReasonEnum.kUserHangup,
        ),
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

    async def blocked_offer(**kwargs: Any) -> dict[str, Any]:
        await release.wait()
        return {"webRtcSessionId": MATTER_SESSION_ID}

    matter_client.send_webrtc_provider_command.side_effect = blocked_offer
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

    # Candidate arrives while ProvideOffer is still blocked -> buffered.
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
    assert matter_client.send_device_command.call_count == 0

    # Releasing the offer flushes the buffered candidate.
    release.set()
    await hass.async_block_till_done()
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.WebRtcTransportProvider.Commands.ProvideIceCandidates(
            webRtcSessionID=MATTER_SESSION_ID,
            iceCandidates=[
                clusters.WebRtcTransportDefinitions.Structs.ICECandidateStruct(
                    candidate="c1",
                    sdpMid=NullValue,
                    sdpmLineIndex=0,
                )
            ],
        ),
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_answer_races_offer(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test an answer event dispatched before the ProvideOffer response returns."""

    async def racing_offer(**kwargs: Any) -> dict[str, Any]:
        # The device answer is dispatched before the session id is known.
        callback = _get_webrtc_callback(matter_client)
        callback(
            EventType.WEBRTC_CALLBACK,
            _webrtc_callback_data(matter_node, "answer", {"sdp": "raced"}),
        )
        return {"webRtcSessionId": MATTER_SESSION_ID}

    matter_client.send_webrtc_provider_command.side_effect = racing_offer
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

    # The buffered answer is relayed once the offer completes.
    response = await client.receive_json()
    assert response["event"] == {"type": "answer", "answer": "raced"}


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_offer_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a failing offer cleans up the session."""
    matter_client.send_webrtc_provider_command.side_effect = MatterError("boom")
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
async def test_camera_end_event(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that an 'end' event cleans up so close does not send EndSession."""
    client = await hass_ws_client(hass)
    subscription_id, _ = await _start_session(client, matter_client)

    # The device ends the session.
    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.WEBRTC_CALLBACK,
        data=_webrtc_callback_data(matter_node, "end", {"reason": 11}),
    )

    matter_client.send_device_command.reset_mock()
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": subscription_id,
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    await hass.async_block_till_done()
    assert matter_client.send_device_command.call_count == 0


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_image(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that the camera returns the placeholder still image."""
    image = await async_get_image(hass, ENTITY_ID)
    assert image.content == PLACEHOLDER.read_bytes()
