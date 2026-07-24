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


@pytest.fixture(autouse=True)
def mock_stream_allocate(matter_client: MagicMock) -> None:
    """Mock VideoStreamAllocate/AudioStreamAllocate so offers can allocate a stream."""
    matter_client.send_device_command.return_value = {
        "videoStreamID": 10,
        "audioStreamID": 11,
    }


def _video_resolution(width: int, height: int) -> dict[str, int]:
    """Build a tag-based VideoResolutionStruct value."""
    return {"0": width, "1": height}


def _allocated_video_stream(stream_id: int, stream_usage: int = 3) -> dict[str, Any]:
    """Build a tag-based VideoStreamStruct value for AllocatedVideoStreams."""
    return {
        "0": stream_id,
        "1": stream_usage,
        "2": 0,
        "3": 30,
        "4": 30,
        "5": _video_resolution(1920, 1080),
        "6": _video_resolution(1920, 1080),
        "7": 10000,
        "8": 10000,
        "9": 4000,
        "12": 1,
    }


def _allocated_audio_stream(stream_id: int, stream_usage: int = 3) -> dict[str, Any]:
    """Build a tag-based AudioStreamStruct value for AllocatedAudioStreams."""
    return {
        "0": stream_id,
        "1": stream_usage,
        "2": 0,
        "3": 1,
        "4": 48000,
        "5": 20000,
        "6": 24,
        "7": 1,
    }


def _find_command[T](matter_client: MagicMock, command_type: type[T]) -> T:
    """Return the first send_device_command call's command of the given type."""
    for call_args in matter_client.send_device_command.call_args_list:
        command = call_args.kwargs["command"]
        if isinstance(command, command_type):
            return command
    raise AssertionError(f"No {command_type.__name__} command was sent")


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

    # A video/audio stream is allocated with the fallback bounds (the fixture
    # reports no VideoSensorParams/MaxEncodedPixelRate) before the offer.
    video_command = _find_command(
        matter_client, clusters.CameraAvStreamManagement.Commands.VideoStreamAllocate
    )
    assert video_command.streamUsage == clusters.Globals.Enums.StreamUsageEnum.kLiveView
    assert video_command.minFrameRate == 30
    assert video_command.maxFrameRate == 120
    assert (
        video_command.minResolution
        == clusters.CameraAvStreamManagement.Structs.VideoResolutionStruct(
            width=640, height=480
        )
    )
    assert (
        video_command.maxResolution
        == clusters.CameraAvStreamManagement.Structs.VideoResolutionStruct(
            width=1920, height=1080
        )
    )
    audio_command = _find_command(
        matter_client, clusters.CameraAvStreamManagement.Commands.AudioStreamAllocate
    )
    assert audio_command.streamUsage == clusters.Globals.Enums.StreamUsageEnum.kLiveView

    # ProvideOffer is sent to the camera with the frontend offer.
    assert matter_client.send_webrtc_provider_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command_name="ProvideOffer",
        payload={
            "webRtcSessionID": None,
            "sdp": "v=0\r\n",
            "streamUsage": clusters.Globals.Enums.StreamUsageEnum.kLiveView,
            "videoStreamID": 10,
            "audioStreamID": 11,
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
    # EndSession and the (concurrently scheduled) owned-stream deallocation are
    # both sent; order between the two isn't guaranteed.
    assert (
        call(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.WebRtcTransportProvider.Commands.EndSession(
                webRtcSessionID=MATTER_SESSION_ID,
                reason=clusters.WebRtcTransportDefinitions.Enums.WebRTCEndReasonEnum.kUserHangup,
            ),
        )
        in matter_client.send_device_command.call_args_list
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
    assert not any(
        isinstance(
            call_args.kwargs["command"],
            clusters.WebRtcTransportProvider.Commands.ProvideIceCandidates,
        )
        for call_args in matter_client.send_device_command.call_args_list
    )

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
async def test_camera_webrtc_reuses_allocated_stream(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that an already allocated stream matching kLiveView is reused."""
    set_node_attribute(
        matter_node, 1, 1361, 15, [_allocated_video_stream(stream_id=42)]
    )
    set_node_attribute(
        matter_node, 1, 1361, 16, [_allocated_audio_stream(stream_id=43)]
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
    await client.receive_json()  # session event

    assert matter_client.send_device_command.call_count == 0
    payload = matter_client.send_webrtc_provider_command.call_args.kwargs["payload"]
    assert payload["videoStreamID"] == 42
    assert payload["audioStreamID"] == 43


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_uses_video_sensor_params(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test max resolution/frame rate come from VideoSensorParams when reported."""
    set_node_attribute(matter_node, 1, 1361, 2, {"0": 3840, "1": 2160, "2": 15})
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
    await client.receive_json()  # session event

    command = _find_command(
        matter_client, clusters.CameraAvStreamManagement.Commands.VideoStreamAllocate
    )
    assert (
        command.maxResolution
        == clusters.CameraAvStreamManagement.Structs.VideoResolutionStruct(
            width=3840, height=2160
        )
    )
    assert command.maxFrameRate == 15
    # minFrameRate is capped to the sensor's max fps (30 would exceed it).
    assert command.minFrameRate == 15


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_caps_frame_rate_by_pixel_rate(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test MaxEncodedPixelRate further caps the requested frame rate."""
    set_node_attribute(matter_node, 1, 1361, 2, {"0": 1920, "1": 1080, "2": 60})
    set_node_attribute(matter_node, 1, 1361, 1, 1920 * 1080 * 24)
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
    await client.receive_json()  # session event

    command = _find_command(
        matter_client, clusters.CameraAvStreamManagement.Commands.VideoStreamAllocate
    )
    # The sensor allows 60 fps, but the encoder's pixel-rate budget only
    # sustains 24 fps at 1920x1080.
    assert command.maxFrameRate == 24
    assert command.minFrameRate == 24


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_stream_id_casing_fallback(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the matterjs-server casing workaround for Allocate responses."""
    matter_client.send_device_command.return_value = {
        "videoStreamId": 20,
        "audioStreamId": 21,
    }
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
    await client.receive_json()  # session event

    payload = matter_client.send_webrtc_provider_command.call_args.kwargs["payload"]
    assert payload["videoStreamID"] == 20
    assert payload["audioStreamID"] == 21


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_audio_allocate_failure_is_video_only(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a failing AudioStreamAllocate falls back to video-only."""

    async def send_device_command(**kwargs: Any) -> dict[str, Any]:
        if isinstance(
            kwargs["command"],
            clusters.CameraAvStreamManagement.Commands.AudioStreamAllocate,
        ):
            raise MatterError("no microphone")
        return {"videoStreamID": 10, "audioStreamID": 11}

    matter_client.send_device_command.side_effect = send_device_command
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
    await client.receive_json()  # session event

    payload = matter_client.send_webrtc_provider_command.call_args.kwargs["payload"]
    assert payload["videoStreamID"] == 10
    assert payload["audioStreamID"] is None


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_deallocates_owned_stream_on_close(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a stream we allocated ourselves is freed once no session uses it."""
    client = await hass_ws_client(hass)
    subscription_id, _ = await _start_session(client, matter_client)

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

    video_deallocate = _find_command(
        matter_client, clusters.CameraAvStreamManagement.Commands.VideoStreamDeallocate
    )
    assert video_deallocate.videoStreamID == 10
    audio_deallocate = _find_command(
        matter_client, clusters.CameraAvStreamManagement.Commands.AudioStreamDeallocate
    )
    assert audio_deallocate.audioStreamID == 11


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_does_not_deallocate_reused_stream_on_close(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a stream allocated by another party isn't deallocated on close."""
    set_node_attribute(
        matter_node, 1, 1361, 15, [_allocated_video_stream(stream_id=42)]
    )
    set_node_attribute(
        matter_node, 1, 1361, 16, [_allocated_audio_stream(stream_id=43)]
    )
    client = await hass_ws_client(hass)
    subscription_id, _ = await _start_session(client, matter_client)

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

    assert not any(
        isinstance(
            call_args.kwargs["command"],
            clusters.CameraAvStreamManagement.Commands.VideoStreamDeallocate
            | clusters.CameraAvStreamManagement.Commands.AudioStreamDeallocate,
        )
        for call_args in matter_client.send_device_command.call_args_list
    )


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
