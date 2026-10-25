"""Test Matter cameras."""

import asyncio
from base64 import b64encode
from collections.abc import Generator
import dataclasses
from typing import Any
from unittest.mock import MagicMock, call, patch

from chip.clusters.Objects import ZoneManagement
from matter_server.client.exceptions import NotConnected
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
import probatio
import pytest
from pytest_homeassistant.common import MockUser
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator
from syrupy.assertion import SnapshotAssertion
from webrtc_models import RTCIceServer

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    CameraState,
    StreamType,
    async_get_image,
    get_camera_from_entity_id,
)
from homeassistant.components.labs import async_update_preview_feature
from homeassistant.components.matter.camera import (
    CAMERA_SCHEMA_VERSION,
    MAX_ICE_SERVERS,
)
from homeassistant.components.matter.const import DOMAIN
from homeassistant.components.web_rtc import async_register_ice_servers
from homeassistant.const import Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import (
    set_node_attribute,
    set_node_attribute_and_notify,
    setup_integration_with_node_fixture,
    snapshot_matter_entities,
    trigger_subscription_callback,
)

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
SNAPSHOT_RESULT = CameraSnapshotResult(
    data=b64encode(b"\xff\xd8snapshot").decode(),
    codec="JPEG",
    resolution=CameraResolution(width=640, height=480),
    degraded=False,
    stream_id=1,
    provenance="allocated",
)
ANSWER_MESSAGE = {"type": "answer", "answer": "v=0\r\nanswer"}
ENDED_MESSAGE = {
    "type": "error",
    "code": "webrtc_session_ended",
    "message": "The camera ended the WebRTC session",
}


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
    client_session_key: str | None,
) -> dict[str, Any]:
    """Build a raw WEBRTC_CALLBACK event payload."""
    return {
        "event_type": event_type,
        "webrtc_session_id": MATTER_SESSION_ID,
        "node_id": matter_node.node_id,
        "endpoint_id": 1,
        "fabric_index": 1,
        "data": data,
        "client_session_key": client_session_key,
    }


def _session_ended_data(
    matter_node: MatterNode, client_session_key: str | None
) -> CameraSessionEndedData:
    """Build a CAMERA_SESSION_ENDED event payload."""
    return CameraSessionEndedData(
        node_id=matter_node.node_id,
        endpoint_id=1,
        webrtc_session_id=MATTER_SESSION_ID,
        cause="peer",
        reason=11,
        client_session_key=client_session_key,
    )


def _block_offer(
    matter_client: MagicMock, result: CameraStartStreamResult | Exception
) -> asyncio.Event:
    """Hold camera_start_stream until the returned event is set."""
    release = asyncio.Event()

    async def blocked_offer(**kwargs: Any) -> CameraStartStreamResult:
        await release.wait()
        if isinstance(result, Exception):
            raise result
        return result

    matter_client.camera_start_stream.side_effect = blocked_offer
    return release


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


async def _send_candidate(client: MockHAClientWebSocket, session_id: str) -> bool:
    """Send a frontend candidate and return whether it was accepted."""
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": ENTITY_ID,
            "session_id": session_id,
            "candidate": {"candidate": "c1", "sdpMLineIndex": 0},
        }
    )
    response = await client.receive_json()
    return response["success"]


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


@pytest.mark.parametrize(
    ("override_attributes", "two_way_audio"),
    [
        pytest.param({}, True, id="full_duplex"),
        pytest.param({"1/1361/9": 1}, True, id="half_duplex"),
        pytest.param({"1/1361/9": 0}, False, id="talk_not_supported"),
        pytest.param({"1/1361/65532": 0b1011}, False, id="no_speaker_feature"),
    ],
)
async def test_camera_capabilities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    override_attributes: dict[str, Any],
    two_way_audio: bool,
) -> None:
    """Test that the camera advertises native WebRTC and two way audio support."""
    # Two way audio is only offered with the labs feature enabled
    assert await async_setup_component(hass, "labs", {})
    await async_update_preview_feature(hass, CAMERA_DOMAIN, "two_way_audio", True)
    await setup_integration_with_node_fixture(
        hass, "mock_camera", matter_client, override_attributes
    )
    camera = get_camera_from_entity_id(hass, ENTITY_ID)
    assert camera.camera_capabilities.frontend_stream_types == {StreamType.WEB_RTC}
    assert camera.camera_capabilities.two_way_audio is two_way_audio


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_capabilities_updated(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test two way audio support follows attribute updates of a loaded camera."""
    assert await async_setup_component(hass, "labs", {})
    await async_update_preview_feature(hass, CAMERA_DOMAIN, "two_way_audio", True)
    camera = get_camera_from_entity_id(hass, ENTITY_ID)
    assert camera.camera_capabilities.two_way_audio is True

    # Dropping the speaker feature disables two way audio.
    await set_node_attribute_and_notify(
        hass,
        matter_client,
        matter_node,
        endpoint=1,
        cluster_id=1361,
        attribute_id=65532,
        value=0b1011,
    )
    assert camera.camera_capabilities.two_way_audio is False

    # Restoring it enables two way audio again.
    await set_node_attribute_and_notify(
        hass,
        matter_client,
        matter_node,
        endpoint=1,
        cluster_id=1361,
        attribute_id=65532,
        value=27,
    )
    assert camera.camera_capabilities.two_way_audio is True

    # The camera reporting that talk is not supported disables it.
    await set_node_attribute_and_notify(
        hass,
        matter_client,
        matter_node,
        endpoint=1,
        cluster_id=1361,
        attribute_id=9,
        value=0,
    )
    assert camera.camera_capabilities.two_way_audio is False


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

    # The frontend offer starts a live view stream named by the session id.
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
        client_session_key=session_id,
        talkback=True,
    )

    # Events of other sessions, and the camera's "end", which is reported
    # again as a session ended event, are not relayed.
    for data in (
        _webrtc_callback_data(matter_node, "answer", {"sdp": "other"}, "other"),
        _webrtc_callback_data(matter_node, "answer", {"sdp": "other"}, None),
        _webrtc_callback_data(matter_node, "end", {"reason": 11}, session_id),
    ):
        await trigger_subscription_callback(
            hass, matter_client, event=EventType.WEBRTC_CALLBACK, data=data
        )

    # The camera answer and candidates are relayed to the frontend.
    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.WEBRTC_CALLBACK,
        data=_webrtc_callback_data(
            matter_node, "answer", {"sdp": "v=0\r\nanswer"}, session_id
        ),
    )
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["event"] == ANSWER_MESSAGE

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
            session_id,
        ),
    )
    response = await client.receive_json()
    assert response["event"]["type"] == "candidate"
    assert response["event"]["candidate"]["candidate"] == "c1"

    # A frontend candidate is forwarded to the camera.
    assert await _send_candidate(client, session_id) is True
    assert matter_client.camera_provide_ice_candidates.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        webrtc_session_id=None,
        ice_candidates=[WebRTCIceCandidate("c1", sdpMid=None, sdpMLineIndex=0)],
        client_session_key=session_id,
    )

    # Closing the session ends it on the camera.
    await _unsubscribe(client, subscription_id)
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        client_session_key=session_id,
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.usefixtures("matter_node")
async def test_camera_webrtc_ice_servers(
    hass: HomeAssistant,
    matter_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the ICE servers are fitted to what the camera accepts."""
    extra_servers = [
        RTCIceServer(urls="stun:empty.example", username="", credential=""),
        RTCIceServer(urls="turn:turn.example", username="user", credential="pass"),
        *(RTCIceServer(urls=f"stun:{index}.example") for index in range(10)),
    ]
    async_register_ice_servers(hass, lambda: extra_servers)

    client = await hass_ws_client(hass)
    await _start_session(client, matter_client)

    # Empty credentials are dropped, and the list is cut after the limit.
    ice_servers = matter_client.camera_start_stream.call_args.kwargs["ice_servers"]
    assert len(ice_servers) == MAX_ICE_SERVERS
    assert ice_servers[1] == {"urls": "stun:empty.example"}
    assert ice_servers[2] == {
        "urls": "turn:turn.example",
        "username": "user",
        "credential": "pass",
    }
    assert ice_servers[-1] == {"urls": "stun:6.example"}


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.usefixtures("matter_node")
async def test_camera_webrtc_candidate_during_offer(
    hass: HomeAssistant,
    matter_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a frontend candidate is forwarded while the offer is in flight."""
    release = _block_offer(matter_client, START_STREAM_RESULT)
    client = await hass_ws_client(hass)
    _, session_id = await _send_offer(client)

    # The server holds the candidate until the camera has the offer.
    assert await _send_candidate(client, session_id) is True
    assert matter_client.camera_provide_ice_candidates.call_count == 1

    release.set()
    await hass.async_block_till_done()


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_closed_during_offer(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test closing a session while the offer is in flight cancels it."""
    release = _block_offer(matter_client, MatterError("Start cancelled"))
    client = await hass_ws_client(hass)
    subscription_id, session_id = await _send_offer(client)

    await _unsubscribe(client, subscription_id)
    release.set()
    await hass.async_block_till_done()

    # The stop cancels the start, whose failure is then expected.
    assert matter_client.camera_stop_stream.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        client_session_key=session_id,
    )
    assert "Error handling WebRTC offer" not in caplog.text


@pytest.mark.parametrize(
    ("camera_events", "expected_messages"),
    [
        pytest.param((), [ENDED_MESSAGE], id="before_answer"),
        pytest.param(("answer",), [ANSWER_MESSAGE, ENDED_MESSAGE], id="after_answer"),
    ],
)
@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_webrtc_session_ended(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
    camera_events: tuple[str, ...],
    expected_messages: list[dict[str, Any]],
) -> None:
    """Test a session that ends without Home Assistant stopping it."""
    client = await hass_ws_client(hass)
    subscription_id, session_id = await _start_session(client, matter_client)
    for event_type in camera_events:
        await trigger_subscription_callback(
            hass,
            matter_client,
            event=EventType.WEBRTC_CALLBACK,
            data=_webrtc_callback_data(
                matter_node, event_type, {"sdp": "v=0\r\nanswer"}, session_id
            ),
        )

    # Only the end of this session counts.
    for key in ("other", None, session_id):
        await trigger_subscription_callback(
            hass,
            matter_client,
            event=EventType.CAMERA_SESSION_ENDED,
            data=_session_ended_data(matter_node, key),
        )

    # The frontend is told so it stops waiting or negotiating.
    for expected_message in expected_messages:
        response = await client.receive_json()
        assert response["id"] == subscription_id
        assert response["event"] == expected_message

    # The session is forgotten, so it takes no candidates and is not stopped.
    assert await _send_candidate(client, session_id) is False
    await _unsubscribe(client, subscription_id)
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_count == 0


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(CameraPrivacyMode(), id="camera_error"),
        pytest.param(NotConnected(), id="client_error"),
    ],
)
@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.usefixtures("matter_node")
async def test_camera_webrtc_offer_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
    error: Exception,
) -> None:
    """Test a failing offer cleans up the session."""
    matter_client.camera_start_stream.side_effect = error
    client = await hass_ws_client(hass)
    _, session_id = await _send_offer(client)

    response = await client.receive_json()
    assert response["event"]["type"] == "error"
    assert response["event"]["code"] == "webrtc_offer_failed"

    # The session was cleaned up, so a later candidate fails.
    assert await _send_candidate(client, session_id) is False


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
    assert f"Error stopping WebRTC session {session_id}: stop failed" in caplog.text


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
async def test_camera_unload_closes_sessions(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that unloading the config entry ends open sessions on the camera."""
    client = await hass_ws_client(hass)
    _, session_id = await _start_session(client, matter_client)

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert matter_client.camera_stop_stream.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        client_session_key=session_id,
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_camera_image(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test snapshots."""
    matter_client.camera_snapshot.return_value = SNAPSHOT_RESULT
    image = await async_get_image(hass, ENTITY_ID)
    assert image.content == b"\xff\xd8snapshot"
    assert image.content_type == "image/jpeg"
    assert matter_client.camera_snapshot.call_args == call(
        node_id=matter_node.node_id, endpoint_id=1, codec="JPEG", resolution=None
    )

    matter_client.camera_snapshot.side_effect = MatterError("boom")
    with pytest.raises(HomeAssistantError, match="boom"):
        await async_get_image(hass, ENTITY_ID)


@pytest.mark.parametrize(
    ("width", "height", "resolution"),
    [
        pytest.param(320, None, {"width": 320}, id="width"),
        pytest.param(None, 240, {"height": 240}, id="height"),
        pytest.param(320, 240, {"width": 320, "height": 240}, id="both"),
    ],
)
@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.usefixtures("matter_node")
async def test_camera_image_resolution(
    hass: HomeAssistant,
    matter_client: MagicMock,
    width: int | None,
    height: int | None,
    resolution: dict[str, int],
) -> None:
    """Test a requested snapshot size is passed on as the server's target."""
    matter_client.camera_snapshot.return_value = SNAPSHOT_RESULT
    camera = get_camera_from_entity_id(hass, ENTITY_ID)
    await camera.async_camera_image(width=width, height=height)
    assert matter_client.camera_snapshot.call_args.kwargs["resolution"] == resolution


# A camera with a 1920x1080 sensor and user-defined zones. Zone 1 came with
# the camera, zones 2 and 3 are user zones, zone 4 has an unknown source and
# zone 5 has no shape.
ZONE_ATTRIBUTES = {
    "1/29/1": [3, 29, 1360, 1361, 1363],
    "1/1360/0": 5,
    "1/1360/1": 6,
    "1/1360/2": [
        {
            "0": 1,
            "1": 0,
            "2": 0,
            "3": {
                "0": "Driveway",
                "1": 0,
                "2": [{"0": 0, "1": 0}, {"0": 960, "1": 0}, {"0": 960, "1": 540}],
                "3": "#FF0000",
            },
        },
        {
            "0": 2,
            "1": 0,
            "2": 1,
            "3": {
                "0": "Window",
                "1": 1,
                "2": [
                    {"0": 1439, "1": 270},
                    {"0": 1919, "1": 270},
                    {"0": 1919, "1": 1079},
                ],
            },
        },
        {
            "0": 3,
            "1": 0,
            "2": 1,
            "3": {
                "0": "Door",
                "1": 0,
                "2": [{"0": 0, "1": 540}, {"0": 480, "1": 540}, {"0": 0, "1": 1079}],
            },
        },
        {
            "0": 4,
            "1": 0,
            "2": 7,
            "3": {
                "0": "Unknown",
                "1": 7,
                "2": [{"0": 0, "1": 0}, {"0": 1, "1": 0}, {"0": 1, "1": 1}],
            },
        },
        {"0": 5, "1": 0, "2": 1},
    ],
    "1/1360/3": [],
    "1/1360/4": 5,
    "1/1360/5": 3,
    "1/1360/6": {"0": 1919, "1": 1079},
    "1/1360/65528": [1],
    "1/1360/65529": [0, 2, 3, 4, 5],
    "1/1360/65531": [0, 1, 2, 3, 4, 5, 6, 65528, 65529, 65531, 65532, 65533],
    "1/1360/65532": 0b0101,
    "1/1360/65533": 1,
    "1/1361/2": {"0": 1920, "1": 1080, "2": 30},
    "1/1361/65531": [2, 9, 20, 21, 65528, 65529, 65531, 65532, 65533],
}
ZONE_FOCUS_ATTRIBUTES = {**ZONE_ATTRIBUTES, "1/1360/65532": 0b1101}
ZONE_DATA = {
    "name": "Garden",
    "use": "privacy",
    "vertices": [{"x": 25, "y": 25}, {"x": 100, "y": 25}, {"x": 100, "y": 100}],
}
ZONE = ZoneManagement.Structs.TwoDCartesianZoneStruct(
    name="Garden",
    use=ZoneManagement.Enums.ZoneUseEnum.kPrivacy,
    vertices=[
        ZoneManagement.Structs.TwoDCartesianVertexStruct(x=480, y=270),
        ZoneManagement.Structs.TwoDCartesianVertexStruct(x=1919, y=270),
        ZoneManagement.Structs.TwoDCartesianVertexStruct(x=1919, y=1079),
    ],
)


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.parametrize("attributes", [ZONE_ATTRIBUTES])
@pytest.mark.usefixtures("matter_node")
async def test_get_camera_zones(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test reading the zones of a camera in percent of the sensor."""
    response = await hass.services.async_call(
        DOMAIN,
        "get_camera_zones",
        target={"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("attributes", "data", "response", "zone_id", "command"),
    [
        pytest.param(
            ZONE_ATTRIBUTES,
            {**ZONE_DATA, "color": "#00FF0080"},
            {"zoneID": 6},
            6,
            ZoneManagement.Commands.CreateTwoDCartesianZone(
                zone=dataclasses.replace(ZONE, color="#00FF0080")
            ),
            id="create",
        ),
        pytest.param(
            ZONE_FOCUS_ATTRIBUTES,
            {**ZONE_DATA, "use": "focus"},
            {"zoneID": 6},
            6,
            ZoneManagement.Commands.CreateTwoDCartesianZone(
                zone=dataclasses.replace(
                    ZONE, use=ZoneManagement.Enums.ZoneUseEnum.kFocus
                )
            ),
            id="create_focus",
        ),
        pytest.param(
            ZONE_ATTRIBUTES,
            {**ZONE_DATA, "zone_id": 2},
            None,
            2,
            ZoneManagement.Commands.UpdateTwoDCartesianZone(zoneID=2, zone=ZONE),
            id="update",
        ),
        pytest.param(
            ZONE_ATTRIBUTES,
            {**ZONE_DATA, "zone_id": 5},
            None,
            5,
            ZoneManagement.Commands.UpdateTwoDCartesianZone(zoneID=5, zone=ZONE),
            id="update_zone_without_shape",
        ),
        pytest.param(
            ZONE_ATTRIBUTES,
            {**ZONE_DATA, "zone_id": 9},
            None,
            9,
            ZoneManagement.Commands.UpdateTwoDCartesianZone(zoneID=9, zone=ZONE),
            id="update_unknown_zone",
        ),
    ],
)
@pytest.mark.parametrize("node_fixture", ["mock_camera"])
async def test_set_camera_zone(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    data: dict[str, Any],
    response: dict[str, Any] | None,
    zone_id: int,
    command: Any,
) -> None:
    """Test setting a zone converts percent to camera coordinates."""
    matter_client.send_device_command.return_value = response
    result = await hass.services.async_call(
        DOMAIN,
        "set_camera_zone",
        data,
        target={"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert result == {ENTITY_ID: {"zone_id": zone_id}}
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id, endpoint_id=1, command=command
    )


@pytest.mark.parametrize(
    "zone_id",
    [
        pytest.param(2, id="privacy_zone"),
        pytest.param(3, id="motion_zone"),
        pytest.param(9, id="unknown_zone"),
    ],
)
@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.parametrize("attributes", [ZONE_ATTRIBUTES])
async def test_clear_camera_zone(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    zone_id: int,
) -> None:
    """Test removing a zone."""
    await hass.services.async_call(
        DOMAIN,
        "clear_camera_zone",
        {"zone_id": zone_id},
        target={"entity_id": ENTITY_ID},
        blocking=True,
    )
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=ZoneManagement.Commands.RemoveZone(zoneID=zone_id),
    )


@pytest.mark.parametrize(
    ("attributes", "action", "data", "message"),
    [
        pytest.param(
            {},
            "set_camera_zone",
            ZONE_DATA,
            "does not support zones",
            id="set_no_zone_cluster",
        ),
        pytest.param(
            {},
            "clear_camera_zone",
            {"zone_id": 2},
            "does not support zones",
            id="clear_no_zone_cluster",
        ),
        pytest.param(
            {**ZONE_ATTRIBUTES, "1/1360/6": None},
            "set_camera_zone",
            ZONE_DATA,
            "does not support zones",
            id="set_no_maximum",
        ),
        pytest.param(
            {**ZONE_ATTRIBUTES, "1/1360/6": {"0": 0, "1": 0}},
            "set_camera_zone",
            ZONE_DATA,
            "does not support zones",
            id="set_zero_maximum",
        ),
        pytest.param(
            {**ZONE_ATTRIBUTES, "1/1360/65532": 0b0001},
            "set_camera_zone",
            ZONE_DATA,
            "does not allow changing its zones",
            id="set_not_editable",
        ),
        pytest.param(
            {**ZONE_ATTRIBUTES, "1/1360/65532": 0b0001},
            "clear_camera_zone",
            {"zone_id": 2},
            "does not allow changing its zones",
            id="clear_not_editable",
        ),
        pytest.param(
            ZONE_ATTRIBUTES,
            "set_camera_zone",
            {**ZONE_DATA, "use": "focus"},
            "does not support focus zones",
            id="set_no_focus",
        ),
        pytest.param(
            ZONE_ATTRIBUTES,
            "set_camera_zone",
            {**ZONE_DATA, "zone_id": 1},
            "Zone 1 of camera.mock_camera is not a user zone and cannot be changed",
            id="set_manufacturer_zone",
        ),
        pytest.param(
            ZONE_ATTRIBUTES,
            "clear_camera_zone",
            {"zone_id": 1},
            "Zone 1 of camera.mock_camera is not a user zone and cannot be removed",
            id="clear_manufacturer_zone",
        ),
        pytest.param(
            ZONE_ATTRIBUTES,
            "clear_camera_zone",
            {"zone_id": 4},
            "Zone 4 of camera.mock_camera is not a user zone and cannot be removed",
            id="clear_unknown_source_zone",
        ),
        pytest.param(
            ZONE_ATTRIBUTES,
            "set_camera_zone",
            {**ZONE_DATA, "zone_id": 4},
            "Zone 4 of camera.mock_camera is not a user zone and cannot be changed",
            id="set_unknown_source_zone",
        ),
        pytest.param(
            ZONE_ATTRIBUTES,
            "set_camera_zone",
            {**ZONE_DATA, "zone_id": 3},
            "Home Assistant cannot change motion zones",
            id="set_motion_zone",
        ),
    ],
)
@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.usefixtures("matter_node")
async def test_camera_zone_not_possible(
    hass: HomeAssistant,
    matter_client: MagicMock,
    action: str,
    data: dict[str, Any],
    message: str,
) -> None:
    """Test zone actions that the camera can't do."""
    with pytest.raises(ServiceValidationError, match=message):
        await hass.services.async_call(
            DOMAIN, action, data, target={"entity_id": ENTITY_ID}, blocking=True
        )
    matter_client.send_device_command.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.parametrize("attributes", [{}])
@pytest.mark.usefixtures("matter_node")
async def test_get_camera_zones_not_supported(hass: HomeAssistant) -> None:
    """Test reading zones of a camera without zones."""
    with pytest.raises(ServiceValidationError, match="does not support zones"):
        await hass.services.async_call(
            DOMAIN,
            "get_camera_zones",
            target={"entity_id": ENTITY_ID},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({**ZONE_DATA, "use": "motion"}, id="motion"),
        pytest.param({**ZONE_DATA, "name": " "}, id="blank_name"),
        pytest.param({**ZONE_DATA, "name": "a" * 33}, id="long_name"),
        pytest.param({**ZONE_DATA, "name": "\u00e4" * 17}, id="long_name_bytes"),
        pytest.param({**ZONE_DATA, "vertices": ZONE_DATA["vertices"][:2]}, id="two"),
        pytest.param({**ZONE_DATA, "vertices": [{"x": 101, "y": 0}] * 3}, id="x_101"),
        pytest.param({**ZONE_DATA, "vertices": [{"x": 0, "y": 101}] * 3}, id="y_101"),
        pytest.param(
            {**ZONE_DATA, "vertices": [{"x": -1, "y": 0}] * 3}, id="x_negative"
        ),
        pytest.param({**ZONE_DATA, "zone_id": 65535}, id="zone_id_65535"),
        pytest.param({**ZONE_DATA, "color": "#FFF"}, id="color_short"),
        pytest.param({**ZONE_DATA, "color": "red"}, id="color_name"),
        pytest.param({**ZONE_DATA, "color": "#FF0000\n"}, id="color_newline"),
    ],
)
@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.parametrize("attributes", [ZONE_ATTRIBUTES])
@pytest.mark.usefixtures("matter_node")
async def test_set_camera_zone_invalid(
    hass: HomeAssistant, matter_client: MagicMock, data: dict[str, Any]
) -> None:
    """Test invalid zones are rejected."""
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "set_camera_zone",
            data,
            target={"entity_id": ENTITY_ID},
            blocking=True,
        )
    matter_client.send_device_command.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.parametrize("attributes", [ZONE_ATTRIBUTES])
async def test_set_camera_zone_longest_name(
    hass: HomeAssistant, matter_client: MagicMock, matter_node: MatterNode
) -> None:
    """Test a name of exactly 32 bytes is accepted."""
    await hass.services.async_call(
        DOMAIN,
        "set_camera_zone",
        {**ZONE_DATA, "zone_id": 2, "name": "\u00e4" * 16},
        target={"entity_id": ENTITY_ID},
        blocking=True,
    )
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=ZoneManagement.Commands.UpdateTwoDCartesianZone(
            zoneID=2, zone=dataclasses.replace(ZONE, name="\u00e4" * 16)
        ),
    )


@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.parametrize("attributes", [ZONE_ATTRIBUTES])
@pytest.mark.usefixtures("matter_node")
async def test_camera_zone_command_error(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Test a camera refusing a zone command."""
    matter_client.send_device_command.side_effect = MatterError("RESOURCE_EXHAUSTED")
    with pytest.raises(HomeAssistantError, match="RESOURCE_EXHAUSTED"):
        await hass.services.async_call(
            DOMAIN,
            "set_camera_zone",
            ZONE_DATA,
            target={"entity_id": ENTITY_ID},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("action", "data"),
    [
        pytest.param("set_camera_zone", ZONE_DATA, id="set"),
        pytest.param("clear_camera_zone", {"zone_id": 2}, id="clear"),
    ],
)
@pytest.mark.parametrize("node_fixture", ["mock_camera"])
@pytest.mark.parametrize("attributes", [ZONE_ATTRIBUTES])
@pytest.mark.usefixtures("matter_node")
async def test_camera_zone_requires_admin(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
    matter_client: MagicMock,
    action: str,
    data: dict[str, Any],
) -> None:
    """Test changing zones requires an admin user."""
    # Grant control of all entities, so the call is only rejected for not being admin
    hass_read_only_user.mock_policy({"entities": {"all": {"control": True}}})
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            action,
            data,
            target={"entity_id": ENTITY_ID},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    matter_client.send_device_command.assert_not_called()
