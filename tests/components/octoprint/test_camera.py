"""The tests for Octoptint camera module."""

from http import HTTPStatus
import json
from typing import Any

import httpx
import pytest
import respx

from homeassistant.components import camera
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.typing import MockHAClientWebSocket, WebSocketGenerator

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform."""
    return Platform.CAMERA


@pytest.fixture
def stream_url() -> str:
    """Fixture for stream URL of the Octoprint camera."""

    return "/webcam/?action=stream"


@pytest.fixture
def snapshot_url() -> str:
    """Fixture for the snapshot URL of the Octoprint camera."""

    return "http://127.0.0.1:8080/?action=snapshot"


@pytest.fixture
def webcam_enabled() -> bool:
    """Fixture for the enablement state of the Octoprint camera."""

    return True


@pytest.fixture
def webcam(stream_url: str, snapshot_url: str, webcam_enabled: bool) -> dict[str, Any]:
    """Fixture for the webcam settings for an Octoprint camera."""

    return {
        "base_url": "http://fake-octoprint/",
        "raw": {
            "streamUrl": stream_url,
            "snapshotUrl": snapshot_url,
            "webcamEnabled": webcam_enabled,
            "snapshotSslValidation": False,
        },
    }


@pytest.mark.parametrize(
    ("stream_url", "expected_stream_types"),
    [
        ("/webcam/?action=stream", set()),
        ("/webcam/stream.m3u8", {camera.StreamType.HLS}),
        ("webrtc://fake-webcam/stream", {camera.StreamType.WEB_RTC}),
        ("webrtcs://fake-webcam/stream", {camera.StreamType.WEB_RTC}),
    ],
)
async def test_camera(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    expected_stream_types: set[camera.StreamType],
) -> None:
    """Test the underlying camera is created and of the correct type."""

    entry = entity_registry.async_get("camera.octoprint_camera")
    assert entry is not None
    assert entry.unique_id == "uuid"

    entity = hass.data.get(camera.DOMAIN).get_entity("camera.octoprint_camera")
    assert entity.camera_capabilities.frontend_stream_types == expected_stream_types


@pytest.mark.parametrize("webcam_enabled", [False])
async def test_camera_disabled(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that the camera does not load if there is not one configured."""
    entry = entity_registry.async_get("camera.octoprint_camera")
    assert entry is None


@pytest.mark.parametrize("webcam", [None])
async def test_no_supported_camera(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that the camera does not load if there is not one configured."""
    entry = entity_registry.async_get("camera.octoprint_camera")
    assert entry is None


@pytest.mark.parametrize(
    "stream_url", ["/webcam/stream.m3u8", "webrtc://fake-webcam/stream"]
)
@pytest.mark.parametrize(
    "snapshot_url", ["http://127.0.0.1:8080/?action=snapshot", None]
)
async def test_use_stream_for_stills(
    hass: HomeAssistant, snapshot_url: str | None
) -> None:
    """Test that the stream is used for stills only when there is not snapshot URL."""

    entity = hass.data.get(camera.DOMAIN).get_entity("camera.octoprint_camera")
    assert entity.use_stream_for_stills == (not snapshot_url)


FAKE_IMAGE = b"fake image"


@respx.mock
@pytest.mark.parametrize("stream_url", ["webrtc://fake-webcam/stream"])
async def test_camera_image(hass: HomeAssistant, snapshot_url: str) -> None:
    """Test getting the camera image from the snapshot URL."""

    entity = hass.data.get(camera.DOMAIN).get_entity("camera.octoprint_camera")
    entity._attr_frame_interval = 3600  # Increase frame interval from the default to make the test timing-resistant

    respx.get(snapshot_url).respond(content=FAKE_IMAGE)
    assert await entity.async_camera_image() == FAKE_IMAGE

    # A second request within the frame interval reuses the cached image, without contacting the server again
    respx.get(snapshot_url).respond(content=b"different image")
    assert await entity.async_camera_image() == FAKE_IMAGE


@respx.mock
@pytest.mark.parametrize("stream_url", ["webrtc://fake-webcam/stream"])
async def test_camera_image_error(hass: HomeAssistant, snapshot_url: str) -> None:
    """Test errors while getting the camera image from the snapshot URL."""

    entity = hass.data.get(camera.DOMAIN).get_entity("camera.octoprint_camera")
    entity._last_image = FAKE_IMAGE  # Errors should return the cached image

    respx.get(snapshot_url).respond(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    assert await entity.async_camera_image() == FAKE_IMAGE


@respx.mock
@pytest.mark.parametrize("stream_url", ["webrtc://fake-webcam/stream"])
async def test_camera_image_timeout(hass: HomeAssistant, snapshot_url: str) -> None:
    "Test a timeout while getting the camera image from the snapshot URL."

    entity = hass.data.get(camera.DOMAIN).get_entity("camera.octoprint_camera")
    entity._last_image = FAKE_IMAGE  # Timeouts should return the cached image

    respx.get(snapshot_url).mock(side_effect=httpx.TimeoutException)
    assert await entity.async_camera_image() == FAKE_IMAGE


async def send_offer_for_mock_response(
    *, stream_url: str, client: MockHAClientWebSocket, **kwargs: Any
):
    """Send an SDP offer via web-socket, with mocking of the response, and validate that it was sent successfully."""

    OFFER_SDP = "v=0\r\n"

    respx.post(f"http{stream_url[6:]}").respond(**kwargs)
    await client.send_json(
        {
            "id": 1,
            "type": "camera/webrtc/offer",
            "entity_id": "camera.octoprint_camera",
            "offer": OFFER_SDP,
        }
    )

    response = await client.receive_json()
    assert response["id"] == 1
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    assert response["result"] is None

    response = await client.receive_json()
    assert response["id"] == 1
    assert response["type"] == "event"
    assert response["event"]["type"] == "session"
    assert response["event"]["session_id"]

    request = json.loads(respx.calls.last.request.content)
    assert request["type"] == "offer"
    assert request["sdp"] == OFFER_SDP


@respx.mock
@pytest.mark.parametrize("stream_url", ["webrtc://fake-webcam/stream"])
async def test_webrtc_offer(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stream_url: str,
) -> None:
    """Test that WebRTC offers are sent as HTTP POSTs and the answer reported."""

    ANSWER_SDP = "v=1\r\n"

    client = await hass_ws_client(hass)
    await send_offer_for_mock_response(
        stream_url=stream_url,
        client=client,
        status_code=HTTPStatus.OK,
        json={"type": "answer", "sdp": ANSWER_SDP},
    )

    response = await client.receive_json()
    assert response["id"] == 1
    assert response["type"] == "event"
    assert response["event"]["type"] == "answer"
    assert response["event"]["answer"] == ANSWER_SDP


@respx.mock
@pytest.mark.parametrize("stream_url", ["webrtc://fake-webcam/stream"])
async def test_webrtc_offer_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stream_url: str,
) -> None:
    """Test that WebRTC offer HTTP failures are reported via websocket."""

    client = await hass_ws_client(hass)
    await send_offer_for_mock_response(
        stream_url=stream_url,
        client=client,
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    response = await client.receive_json()
    assert response["id"] == 1
    assert response["type"] == "event"
    assert response["event"]["type"] == "error"
    assert response["event"]["code"] == "webrtc_offer_failed"
    assert "500" in response["event"]["message"]


@respx.mock
@pytest.mark.parametrize("stream_url", ["webrtc://fake-webcam/stream"])
@pytest.mark.parametrize("invalid_response", [b"not json", b"{}"])
async def test_webrtc_offer_invalid(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stream_url: str,
    invalid_response: bytes,
) -> None:
    """Test that WebRTC offers with invalid responses are reported via websocket."""

    client = await hass_ws_client(hass)
    await send_offer_for_mock_response(
        stream_url=stream_url,
        client=client,
        status_code=HTTPStatus.OK,
        content=invalid_response,
    )

    response = await client.receive_json()
    assert response["id"] == 1
    assert response["type"] == "event"
    assert response["event"]["type"] == "error"
    assert response["event"]["code"] == "webrtc_offer_failed"
    assert "Invalid answer" in response["event"]["message"]
