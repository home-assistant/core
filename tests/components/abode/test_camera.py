"""Tests for the Abode camera device."""

import asyncio
import base64
import json
import time
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, PropertyMock, patch

from aiohttp import ClientError, WSMsgType
from jaraco.abode.exceptions import Exception as AbodeException
import pytest
from requests.exceptions import HTTPError
from webrtc_models import RTCIceServer

from homeassistant.components.abode.camera import (
    KVS_SIGNALING_ACTION_ICE_CANDIDATE,
    KVS_SIGNALING_ACTION_SDP_OFFER,
    MEDIA_PLAYBACK_URL,
    AbodeCamera,
    _AbodeWebRTCSession,
)
from homeassistant.components.abode.const import DOMAIN
from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    CameraState,
    RTCIceCandidateInit,
    WebRTCAnswer,
    WebRTCCandidate,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.components.camera.helper import get_camera_from_entity_id
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


def _kvs_signaling_message(message_type: str, payload: dict[str, str | int]) -> Any:
    """Create a fake KVS signaling websocket text message."""
    encoded_payload = base64.b64encode(json.dumps(payload).encode()).decode()
    return SimpleNamespace(
        type=WSMsgType.TEXT,
        data=json.dumps(
            {"messageType": message_type, "messagePayload": encoded_payload}
        ),
    )


class _FakeWebSocket:
    """Simple websocket stub for Abode WebRTC tests."""

    def __init__(self, messages: list[Any] | None = None) -> None:
        self._messages = messages or []
        self._index = 0
        self.sent_json: list[dict[str, Any]] = []
        self.closed = False

    async def send_json(self, payload: dict[str, Any]) -> None:
        """Capture sent websocket JSON payloads."""
        self.sent_json.append(payload)

    async def receive(self) -> Any:
        """Return queued websocket messages."""
        await asyncio.sleep(0)
        if self._index < len(self._messages):
            msg = self._messages[self._index]
            self._index += 1
            return msg
        return SimpleNamespace(type=WSMsgType.CLOSED, data=None)

    async def close(self) -> None:
        """Mark websocket closed."""
        self.closed = True

    def exception(self) -> None:
        """Return websocket exception state."""
        return None  # noqa: RET501


class _FakeClientSession:
    """Simple aiohttp client session stub for ws_connect."""

    def __init__(self, ws: _FakeWebSocket) -> None:
        self.ws = ws
        self.connected_url: str | None = None

    async def ws_connect(self, url: str) -> _FakeWebSocket:
        """Return the fake websocket."""
        self.connected_url = url
        return self.ws


async def test_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, CAMERA_DOMAIN)

    entry = entity_registry.async_get("camera.test_cam")
    assert entry.unique_id == "d0a3a1c316891ceb00c20118aae2a133"


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the camera attributes are correct."""
    await setup_platform(hass, CAMERA_DOMAIN)

    state = hass.states.get("camera.test_cam")
    assert state.state == CameraState.IDLE


async def test_capture_image(hass: HomeAssistant) -> None:
    """Test the camera capture image service."""
    await setup_platform(hass, CAMERA_DOMAIN)

    with patch("jaraco.abode.devices.camera.Camera.capture") as mock_capture:
        await hass.services.async_call(
            DOMAIN,
            "capture_image",
            {ATTR_ENTITY_ID: "camera.test_cam"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_capture.assert_called_once()


async def test_camera_on(hass: HomeAssistant) -> None:
    """Test the camera turn on service."""
    await setup_platform(hass, CAMERA_DOMAIN)

    with patch("jaraco.abode.devices.camera.Camera.privacy_mode") as mock_capture:
        await hass.services.async_call(
            CAMERA_DOMAIN,
            "turn_on",
            {ATTR_ENTITY_ID: "camera.test_cam"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_capture.assert_called_once_with(False)


async def test_camera_off(hass: HomeAssistant) -> None:
    """Test the camera turn off service."""
    await setup_platform(hass, CAMERA_DOMAIN)

    with patch("jaraco.abode.devices.camera.Camera.privacy_mode") as mock_capture:
        await hass.services.async_call(
            CAMERA_DOMAIN,
            "turn_off",
            {ATTR_ENTITY_ID: "camera.test_cam"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_capture.assert_called_once_with(True)


async def test_camera_image_uses_snapshot_for_new_camera(hass: HomeAssistant) -> None:
    """Test new Abode camera images are fetched via snapshot endpoint."""
    await setup_platform(hass, CAMERA_DOMAIN)

    image_bytes = b"snapshot-bytes"
    snapshot_data_url = (
        f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('ascii')}"
    )

    with (
        patch(
            "jaraco.abode.devices.camera.Camera.snapshot",
            return_value=True,
        ) as mock_snapshot,
        patch(
            "jaraco.abode.devices.camera.Camera.snapshot_data_url",
            return_value=snapshot_data_url,
        ) as mock_snapshot_data_url,
        patch("jaraco.abode.devices.camera.Camera.refresh_image") as mock_refresh_image,
        patch(
            "homeassistant.components.abode.camera.requests.get"
        ) as mock_requests_get,
    ):
        image = await async_get_image(hass, "camera.test_cam")

    assert image.content == image_bytes
    mock_snapshot.assert_called_once()
    mock_snapshot_data_url.assert_called_once_with(get_snapshot=False)
    mock_refresh_image.assert_not_called()
    mock_requests_get.assert_not_called()


async def test_camera_image_snapshot_fallback_to_timeline(hass: HomeAssistant) -> None:
    """Test new camera falls back to timeline image flow if snapshot fails."""
    await setup_platform(hass, CAMERA_DOMAIN)

    response = Mock()
    response.content = b"timeline-image"
    response.raise_for_status.return_value = None

    with (
        patch(
            "jaraco.abode.devices.camera.Camera.snapshot",
            return_value=False,
        ) as mock_snapshot,
        patch(
            "jaraco.abode.devices.camera.Camera.refresh_image",
            return_value=True,
        ) as mock_refresh_image,
        patch(
            "jaraco.abode.devices.camera.Camera.image_url",
            new_callable=PropertyMock,
            return_value="https://example.com/image.jpg",
        ),
        patch(
            "homeassistant.components.abode.camera.requests.get",
            return_value=response,
        ) as mock_requests_get,
    ):
        image = await async_get_image(hass, "camera.test_cam")

    assert image.content == b"timeline-image"
    mock_snapshot.assert_called_once()
    mock_refresh_image.assert_called_once()
    mock_requests_get.assert_called_once()


async def test_snapshot_failure_keeps_last_snapshot_image(hass: HomeAssistant) -> None:
    """Test snapshot failures keep last good snapshot image."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    image_bytes = b"snapshot-bytes"
    snapshot_data_url = (
        f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('ascii')}"
    )

    with (
        patch(
            "jaraco.abode.devices.camera.Camera.snapshot",
            side_effect=[True, False],
        ) as mock_snapshot,
        patch(
            "jaraco.abode.devices.camera.Camera.snapshot_data_url",
            return_value=snapshot_data_url,
        ),
    ):
        assert camera._refresh_snapshot_image() is True
        assert camera._snapshot_image == image_bytes
        assert camera._refresh_snapshot_image() is False

    assert camera._snapshot_image == image_bytes
    assert mock_snapshot.call_count == 2


async def test_camera_stream_source_uses_hls_playback_url(hass: HomeAssistant) -> None:
    """Test stream source is fetched from Abode playback URL endpoint."""
    await setup_platform(hass, CAMERA_DOMAIN)

    response = Mock()
    response.json.return_value = {"playbackUrl": "https://example.com/live.m3u8"}

    with (
        patch("homeassistant.components.abode.camera.time.time", return_value=12345),
        patch(
            "jaraco.abode.client.Client.send_request", return_value=response
        ) as mock_send,
    ):
        stream_source = await async_get_stream_source(hass, "camera.test_cam")

    assert stream_source == "https://example.com/live.m3u8"
    mock_send.assert_called_once_with(
        "post",
        MEDIA_PLAYBACK_URL,
        data={
            "cameraId": "XF:b0c5ba27592a",
            "startTime": 12315,
            "format": "hls",
            "playbackMode": "LIVE_REPLAY",
        },
    )


async def test_camera_stream_source_returns_none_without_playback_url(
    hass: HomeAssistant,
) -> None:
    """Test stream source falls back to none when playback URL is not returned."""
    await setup_platform(hass, CAMERA_DOMAIN)

    response = Mock()
    response.json.return_value = {}

    with patch("jaraco.abode.client.Client.send_request", return_value=response):
        stream_source = await async_get_stream_source(hass, "camera.test_cam")

    assert stream_source is None


async def test_camera_webrtc_client_config_uses_kvs_ice_servers(
    hass: HomeAssistant,
) -> None:
    """Test WebRTC client configuration uses Abode-provided ICE servers."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))

    response = Mock()
    response.json.return_value = {
        "channelEndpoint": "wss://example.com/signaling",
        "iceServers": [
            {
                "urls": ["stun:stun.kinesisvideo.us-east-1.amazonaws.com:443"],
                "username": "user",
                "credential": "pass",
            }
        ],
    }

    with patch("jaraco.abode.client.Client.send_request", return_value=response):
        assert await camera._async_refresh_kvs_signaling_info() is not None

    config = camera.async_get_webrtc_client_configuration().to_frontend_dict()
    assert config["configuration"]["iceServers"][0] == {
        "urls": ["stun:stun.kinesisvideo.us-east-1.amazonaws.com:443"],
        "username": "user",
        "credential": "pass",
    }


async def test_camera_webrtc_offer_sends_offer_and_receives_events(
    hass: HomeAssistant,
) -> None:
    """Test WebRTC offer sends signaling offer and emits answer/candidate."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))

    response = Mock()
    response.json.return_value = {
        "channelEndpoint": "wss://example.com/signaling",
        "iceServers": [],
    }
    ws = _FakeWebSocket(
        [
            _kvs_signaling_message("SDP_ANSWER", {"type": "answer", "sdp": "answer-sdp"}),
            _kvs_signaling_message(
                "ICE_CANDIDATE",
                {
                    "candidate": "candidate:0 1 UDP 2122252543 192.0.2.1 5000 typ host",
                    "sdpMid": "0",
                    "sdpMLineIndex": 0,
                },
            ),
            SimpleNamespace(type=WSMsgType.CLOSED, data=None),
        ]
    )
    session = _FakeClientSession(ws)
    events: list[Any] = []

    with (
        patch("jaraco.abode.client.Client.send_request", return_value=response),
        patch(
            "homeassistant.components.abode.camera.async_get_clientsession",
            return_value=session,
        ),
    ):
        await camera.async_handle_async_webrtc_offer(
            "offer-sdp",
            "session-1",
            events.append,
        )
        await hass.async_block_till_done()

    assert session.connected_url == "wss://example.com/signaling"
    assert ws.sent_json
    assert ws.sent_json[0]["action"] == KVS_SIGNALING_ACTION_SDP_OFFER
    sent_offer = json.loads(base64.b64decode(ws.sent_json[0]["messagePayload"]))
    assert sent_offer == {"type": "offer", "sdp": "offer-sdp"}
    assert any(isinstance(event, WebRTCAnswer) for event in events)
    assert any(isinstance(event, WebRTCCandidate) for event in events)
    assert "session-1" not in camera._webrtc_sessions


async def test_camera_webrtc_candidate_sends_signaling_message(
    hass: HomeAssistant,
) -> None:
    """Test WebRTC candidates are forwarded to KVS signaling websocket."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    ws = _FakeWebSocket()
    camera._webrtc_sessions["session-candidate"] = _AbodeWebRTCSession(ws=ws)

    await camera.async_on_webrtc_candidate(
        "session-candidate",
        RTCIceCandidateInit(
            "candidate:0 1 UDP 2122252543 192.0.2.1 5000 typ host",
            sdp_mid="0",
            sdp_m_line_index=0,
        ),
    )

    assert ws.sent_json
    assert ws.sent_json[0]["action"] == KVS_SIGNALING_ACTION_ICE_CANDIDATE


async def test_camera_webrtc_candidate_ignores_unknown_session(
    hass: HomeAssistant,
) -> None:
    """Test unknown WebRTC candidate sessions are ignored."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))

    await camera.async_on_webrtc_candidate(
        "unknown-session",
        RTCIceCandidateInit(
            "candidate:0 1 UDP 2122252543 192.0.2.1 5000 typ host",
            sdp_mid="0",
            sdp_m_line_index=0,
        ),
    )


async def test_camera_refresh_image_handles_auth_error(hass: HomeAssistant) -> None:
    """Test camera image refresh handles Abode auth errors without raising."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))

    with (
        patch(
            "jaraco.abode.devices.camera.Camera.snapshot",
            return_value=False,
        ),
        patch(
            "jaraco.abode.devices.camera.Camera.refresh_image",
            side_effect=AbodeException((403, "forbidden")),
        ),
    ):
        image = await hass.async_add_executor_job(camera.camera_image)

    assert image is None


async def test_camera_snapshot_refresh_handles_snapshot_error(hass: HomeAssistant) -> None:
    """Test snapshot refresh returns False when snapshot request raises."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))

    with patch(
        "jaraco.abode.devices.camera.Camera.snapshot",
        side_effect=AbodeException((403, "forbidden")),
    ):
        assert camera._refresh_snapshot_image() is False


async def test_camera_snapshot_refresh_invalid_snapshot_format(
    hass: HomeAssistant,
) -> None:
    """Test snapshot refresh handles malformed snapshot data url."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))

    with (
        patch("jaraco.abode.devices.camera.Camera.snapshot", return_value=True),
        patch(
            "jaraco.abode.devices.camera.Camera.snapshot_data_url",
            return_value="invalid-format",
        ),
    ):
        assert camera._refresh_snapshot_image() is False


async def test_camera_snapshot_refresh_invalid_base64(hass: HomeAssistant) -> None:
    """Test snapshot refresh handles invalid base64 payloads."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))

    with (
        patch("jaraco.abode.devices.camera.Camera.snapshot", return_value=True),
        patch(
            "jaraco.abode.devices.camera.Camera.snapshot_data_url",
            return_value="data:image/jpeg;base64,a",
        ),
    ):
        assert camera._refresh_snapshot_image() is False


async def test_camera_get_image_handles_http_error(hass: HomeAssistant) -> None:
    """Test timeline image fetch handles HTTP errors."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    response = Mock()
    response.raise_for_status.side_effect = HTTPError("boom")

    with (
        patch(
            "jaraco.abode.devices.camera.Camera.image_url",
            new_callable=PropertyMock,
            return_value="https://example.com/image.jpg",
        ),
        patch(
            "homeassistant.components.abode.camera.requests.get",
            return_value=response,
        ),
    ):
        camera.get_image()

    assert camera._response is None


async def test_camera_get_image_without_image_url(hass: HomeAssistant) -> None:
    """Test timeline image fetch clears response when URL is missing."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    camera._response = Mock()

    with patch(
        "jaraco.abode.devices.camera.Camera.image_url",
        new_callable=PropertyMock,
        return_value=None,
    ):
        camera.get_image()

    assert camera._response is None


async def test_camera_stream_source_handles_request_error(hass: HomeAssistant) -> None:
    """Test stream source returns None when Abode request fails."""
    await setup_platform(hass, CAMERA_DOMAIN)

    with patch(
        "jaraco.abode.client.Client.send_request",
        side_effect=AbodeException((500, "error")),
    ):
        stream_source = await async_get_stream_source(hass, "camera.test_cam")

    assert stream_source is None


async def test_camera_stream_source_returns_none_when_snapshot_not_supported(
    hass: HomeAssistant,
) -> None:
    """Test stream_source returns None for non-snapshot cameras."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    camera._supports_snapshot = False
    assert await camera.stream_source() is None


async def test_camera_refresh_kvs_signaling_info_uses_cache(
    hass: HomeAssistant,
) -> None:
    """Test KVS signaling refresh uses cached endpoint/ICE servers."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    camera._kvs_channel_endpoint = "wss://example.com/signaling"
    camera._webrtc_ice_servers = [RTCIceServer(urls=["stun:example"])]
    camera._kvs_signaling_last_refresh_monotonic = time.monotonic()

    with patch.object(camera, "_get_kvs_signaling_info") as mock_refresh:
        cached = await camera._async_refresh_kvs_signaling_info()

    assert cached is not None
    assert cached["channelEndpoint"] == "wss://example.com/signaling"
    assert mock_refresh.call_count == 0


async def test_camera_get_kvs_signaling_info_requires_channel_endpoint(
    hass: HomeAssistant,
) -> None:
    """Test KVS signaling metadata requires a channel endpoint."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    response = Mock()
    response.json.return_value = {}

    with (
        patch("jaraco.abode.client.Client.send_request", return_value=response),
        pytest.raises(HomeAssistantError, match="Missing KVS channel endpoint"),
    ):
        camera._get_kvs_signaling_info()


async def test_camera_get_kvs_signaling_info_requires_dict_response(
    hass: HomeAssistant,
) -> None:
    """Test KVS signaling metadata requires JSON object response."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    response = Mock()
    response.json.return_value = []

    with (
        patch("jaraco.abode.client.Client.send_request", return_value=response),
        pytest.raises(HomeAssistantError, match="Invalid KVS signaling response"),
    ):
        camera._get_kvs_signaling_info()


async def test_camera_async_refresh_kvs_signaling_info_handles_exception(
    hass: HomeAssistant,
) -> None:
    """Test KVS signaling async refresh handles unexpected exceptions."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))

    with patch.object(
        camera,
        "_get_kvs_signaling_info",
        side_effect=RuntimeError("boom"),
    ):
        assert await camera._async_refresh_kvs_signaling_info(force=True) is None


def test_parse_ice_servers_handles_invalid_entries() -> None:
    """Test ICE server parser skips invalid entries."""
    assert AbodeCamera._parse_ice_servers("invalid") == []
    parsed = AbodeCamera._parse_ice_servers(
        [
            1,
            {"urls": 1},
            {"urls": "stun:example"},
            {"urls": ["turn:example"], "username": 1, "credential": 2},
        ]
    )
    assert len(parsed) == 2
    assert parsed[0].urls == "stun:example"
    assert parsed[1].urls == ["turn:example"]
    assert parsed[1].username is None
    assert parsed[1].credential is None


def test_decode_signaling_message_invalid_payloads() -> None:
    """Test signaling decode returns None for malformed payloads."""
    assert (
        AbodeCamera._decode_signaling_message(
            SimpleNamespace(type=WSMsgType.TEXT, data="not-json")
        )
        is None
    )
    encoded_list_payload = base64.b64encode(json.dumps(["not", "dict"]).encode()).decode()
    assert (
        AbodeCamera._decode_signaling_message(
            SimpleNamespace(
                type=WSMsgType.TEXT,
                data=json.dumps(
                    {"messageType": "SDP_ANSWER", "messagePayload": encoded_list_payload}
                ),
            )
        )
        is None
    )


def test_parse_remote_ice_candidate_fallback_and_invalid() -> None:
    """Test remote ICE candidate parser fallback behavior."""
    with patch(
        "homeassistant.components.abode.camera.RTCIceCandidateInit.from_dict",
        side_effect=ValueError("invalid"),
    ):
        candidate = AbodeCamera._parse_remote_ice_candidate(
            {"candidate": "candidate-line", "sdpMid": 1, "sdpMLineIndex": "0"}
        )

    assert candidate is not None
    assert candidate.candidate == "candidate-line"
    assert candidate.sdp_mid is None
    assert candidate.sdp_m_line_index == 0

    with patch(
        "homeassistant.components.abode.camera.RTCIceCandidateInit.from_dict",
        side_effect=ValueError("invalid"),
    ):
        assert (
            AbodeCamera._parse_remote_ice_candidate({"candidate": 1, "sdpMid": "0"})
            is None
        )


async def test_listen_webrtc_messages_sends_error_event(hass: HomeAssistant) -> None:
    """Test websocket error messages emit WebRTCError and cleanup session."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    ws = _FakeWebSocket([SimpleNamespace(type=WSMsgType.ERROR, data=None)])
    camera._webrtc_sessions["session-error"] = _AbodeWebRTCSession(ws=ws)
    events: list[Any] = []

    await camera._async_listen_webrtc_messages("session-error", ws, events.append)

    assert events
    assert events[0].code == "webrtc_signaling_error"
    assert "session-error" not in camera._webrtc_sessions


async def test_listen_webrtc_messages_ignores_non_text(hass: HomeAssistant) -> None:
    """Test websocket non-text signaling messages are ignored."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    ws = _FakeWebSocket(
        [
            SimpleNamespace(type=WSMsgType.BINARY, data=b"1"),
            SimpleNamespace(type=WSMsgType.CLOSED, data=None),
        ]
    )
    camera._webrtc_sessions["session-binary"] = _AbodeWebRTCSession(ws=ws)
    events: list[Any] = []

    await camera._async_listen_webrtc_messages("session-binary", ws, events.append)

    assert events == []
    assert "session-binary" not in camera._webrtc_sessions


async def test_close_webrtc_session_without_active_session(hass: HomeAssistant) -> None:
    """Test closing unknown WebRTC session is a no-op."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    await camera._async_close_webrtc_session("missing-session")


async def test_close_webrtc_session_cancels_listener_task(hass: HomeAssistant) -> None:
    """Test closing WebRTC session cancels listener task."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    ws = _FakeWebSocket()
    listener_task = hass.async_create_task(asyncio.sleep(10))
    camera._webrtc_sessions["session-cancel"] = _AbodeWebRTCSession(
        ws=ws, listener_task=listener_task
    )

    await camera._async_close_webrtc_session("session-cancel")

    assert listener_task.cancelled()
    assert ws.closed


async def test_camera_webrtc_offer_requires_supported_camera(
    hass: HomeAssistant,
) -> None:
    """Test unsupported cameras reject WebRTC offers."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    camera._supports_snapshot = False

    with pytest.raises(HomeAssistantError, match="does not support WebRTC"):
        await camera.async_handle_async_webrtc_offer("offer-sdp", "session-1", list.append)


async def test_camera_webrtc_offer_fails_when_refresh_fails_and_no_endpoint(
    hass: HomeAssistant,
) -> None:
    """Test offer fails when signaling refresh fails without cached endpoint."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    camera._kvs_channel_endpoint = None

    with (
        patch.object(camera, "_async_refresh_kvs_signaling_info", return_value=None),
        pytest.raises(
            HomeAssistantError, match="Failed to refresh Abode WebRTC signaling info"
        ),
    ):
        await camera.async_handle_async_webrtc_offer("offer-sdp", "session-1", list.append)


async def test_camera_webrtc_offer_fails_without_channel_endpoint(
    hass: HomeAssistant,
) -> None:
    """Test offer fails when no channel endpoint is available."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    camera._kvs_channel_endpoint = None

    with (
        patch.object(camera, "_kvs_signaling_is_fresh", return_value=True),
        pytest.raises(HomeAssistantError, match="Missing Abode WebRTC channel endpoint"),
    ):
        await camera.async_handle_async_webrtc_offer("offer-sdp", "session-1", list.append)


async def test_camera_webrtc_offer_fails_when_ws_connect_fails(
    hass: HomeAssistant,
) -> None:
    """Test offer fails when signaling websocket cannot be opened."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    camera._kvs_channel_endpoint = "wss://example.com/signaling"
    session = Mock()
    session.ws_connect.side_effect = ClientError("connect-failed")

    with (
        patch.object(camera, "_kvs_signaling_is_fresh", return_value=True),
        patch(
            "homeassistant.components.abode.camera.async_get_clientsession",
            return_value=session,
        ),
        pytest.raises(
            HomeAssistantError, match="Failed to connect to Abode WebRTC signaling endpoint"
        ),
    ):
        await camera.async_handle_async_webrtc_offer("offer-sdp", "session-1", list.append)


async def test_camera_webrtc_offer_fails_when_offer_send_fails(
    hass: HomeAssistant,
) -> None:
    """Test offer send failures cleanup the WebRTC session."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    camera._kvs_channel_endpoint = "wss://example.com/signaling"
    ws = _FakeWebSocket()

    async def _raise_send_json(payload: dict[str, Any]) -> None:
        raise ClientError("send-failed")

    ws.send_json = _raise_send_json  # type: ignore[method-assign]
    session = _FakeClientSession(ws)

    with (
        patch.object(camera, "_kvs_signaling_is_fresh", return_value=True),
        patch(
            "homeassistant.components.abode.camera.async_get_clientsession",
            return_value=session,
        ),
        pytest.raises(HomeAssistantError, match="Failed to send WebRTC offer"),
    ):
        await camera.async_handle_async_webrtc_offer("offer-sdp", "session-send-fail", list.append)

    assert "session-send-fail" not in camera._webrtc_sessions


async def test_camera_webrtc_candidate_send_failure_raises(hass: HomeAssistant) -> None:
    """Test candidate send failures are surfaced."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))
    ws = _FakeWebSocket()

    async def _raise_send_json(payload: dict[str, Any]) -> None:
        raise ClientError("send-failed")

    ws.send_json = _raise_send_json  # type: ignore[method-assign]
    camera._webrtc_sessions["session-candidate-fail"] = _AbodeWebRTCSession(ws=ws)

    with pytest.raises(HomeAssistantError, match="Failed to send WebRTC candidate"):
        await camera.async_on_webrtc_candidate(
            "session-candidate-fail",
            RTCIceCandidateInit(
                "candidate:0 1 UDP 2122252543 192.0.2.1 5000 typ host",
                sdp_mid="0",
                sdp_m_line_index=0,
            ),
        )


async def test_camera_capture_callback_updates_state(hass: HomeAssistant) -> None:
    """Test capture callback updates image location and schedules state update."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))

    with (
        patch.object(camera._device, "update_image_location") as mock_update_image_location,
        patch.object(camera, "get_image") as mock_get_image,
        patch.object(camera, "schedule_update_ha_state") as mock_schedule_update,
    ):
        camera._capture_callback({"id": "capture-id"})

    mock_update_image_location.assert_called_once_with({"id": "capture-id"})
    mock_get_image.assert_called_once()
    mock_schedule_update.assert_called_once()


async def test_camera_is_on_property(hass: HomeAssistant) -> None:
    """Test is_on property forwards device value."""
    await setup_platform(hass, CAMERA_DOMAIN)
    camera = cast(AbodeCamera, get_camera_from_entity_id(hass, "camera.test_cam"))

    with patch(
        "jaraco.abode.devices.camera.Camera.is_on",
        new_callable=PropertyMock,
        return_value=True,
    ):
        assert camera.is_on is True
