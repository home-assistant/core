"""The tests for Octoptint camera module."""
from http import HTTPStatus
import json
from unittest.mock import patch

from pyoctoprintapi import WebcamSettings
import pytest
import respx

import homeassistant.components.camera as camera
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.typing import WebSocketGenerator


@pytest.fixture(name="stream_url")
def stream_url_fixture() -> str:
    "Fixture for stream URL of the Octoprint camera."

    return "/webcam/?action=stream"


@pytest.fixture(name="snapshot_url")
def snapshot_url_fixture() -> str:
    "Fixture for the snapshot URL of the Octoprint camera."

    return "http://127.0.0.1:8080/?action=snapshot"


@pytest.fixture(name="webcam_enabled")
def webcam_enabled_fixture() -> bool:
    "Fixture for the enablement state of the Octoprint camera."

    return True


@pytest.fixture(name="webcam_settings")
def webcam_settings_fixture(
    stream_url: str, snapshot_url: str, webcam_enabled: bool
) -> WebcamSettings:
    "Fixture the webcam settings for an Octoprint camera."

    return WebcamSettings(
        base_url="http://fake-octoprint/",
        raw={
            "streamUrl": stream_url,
            "snapshotUrl": snapshot_url,
            "webcamEnabled": webcam_enabled,
        },
    )


@pytest.fixture(name="octoprint_camera")
async def octoprint_camera_fixture(
    hass: HomeAssistant, webcam_settings: WebcamSettings
) -> str:
    "Fixture that initializes an Octoprint camera and returns the expected entity ID."

    with patch(
        "pyoctoprintapi.OctoprintClient.get_webcam_info",
        return_value=webcam_settings,
    ):
        await init_integration(hass, camera.DOMAIN)

    return "camera.octoprint_camera"


@pytest.mark.parametrize(
    ("stream_url", "expected_stream_type"),
    (
        ("/webcam/?action=stream", None),
        ("/webcam/stream.m3u8", camera.StreamType.HLS),
        ("webrtc://fake-webcam/stream", camera.StreamType.WEB_RTC),
        ("webrtcs://fake-webcam/stream", camera.StreamType.WEB_RTC),
    ),
)
async def test_camera(
    hass: HomeAssistant,
    octoprint_camera: str,
    expected_stream_type: camera.StreamType | None,
) -> None:
    """Test the underlying camera is created and of the correct type."""

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(octoprint_camera)
    assert entry is not None
    assert entry.unique_id == "uuid"

    entity = hass.data.get(camera.DOMAIN).get_entity(octoprint_camera)
    assert entity.frontend_stream_type == expected_stream_type


@pytest.mark.parametrize("webcam_enabled", (False,))
async def test_camera_disabled(hass: HomeAssistant, octoprint_camera: str) -> None:
    """Test that the camera does not load if there is not one configured."""

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(octoprint_camera)
    assert entry is None


@pytest.mark.parametrize("webcam_settings", (None,))
async def test_no_supported_camera(hass: HomeAssistant, octoprint_camera: str) -> None:
    """Test that the camera does not load if there is not one configured."""

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(octoprint_camera)
    assert entry is None


@respx.mock
@pytest.mark.parametrize("stream_url", ("webrtc://fake-webcam/stream",))
async def test_webrtc_offer(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    octoprint_camera: str,
    stream_url: str,
):
    """Test that websocket WebRTC offers are sent as HTTP POSTs."""

    OFFER_SDP = "v=0\r\n"
    ANSWER_SDP = "v=1\r\n"

    respx.post(f"http{stream_url[6:]}").respond(
        status_code=HTTPStatus.OK, json={"type": "answer", "sdp": ANSWER_SDP}
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "camera/web_rtc_offer",
            "entity_id": octoprint_camera,
            "offer": OFFER_SDP,
        }
    )
    response = await client.receive_json()
    assert response["id"] == 1
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    assert response["result"]["answer"] == ANSWER_SDP

    request = json.loads(respx.calls.last.request.content)
    assert request["type"] == "offer"
    assert request["sdp"] == OFFER_SDP


@respx.mock
@pytest.mark.parametrize("stream_url", ("webrtc://fake-webcam/stream",))
async def test_webrtc_offer_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    octoprint_camera: str,
    stream_url: str,
):
    """Test that websocket WebRTC offer HTTP failures are reported."""

    respx.post(f"http{stream_url[6:]}").respond(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 2,
            "type": "camera/web_rtc_offer",
            "entity_id": octoprint_camera,
            "offer": "v=0\r\n",
        }
    )
    response = await client.receive_json()
    assert response["id"] == 2
    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert "500" in response["error"]["message"]


@respx.mock
@pytest.mark.parametrize("stream_url", ("webrtc://fake-webcam/stream",))
@pytest.mark.parametrize("invalid_response", (b"not json", b"{}"))
async def test_webrtc_offer_invalid(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    octoprint_camera: str,
    stream_url: str,
    invalid_response: bytes,
):
    """Test that websocket WebRTC offers with invalid responses are reported."""

    respx.post(f"http{stream_url[6:]}").respond(
        status_code=HTTPStatus.OK, content=invalid_response
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 3,
            "type": "camera/web_rtc_offer",
            "entity_id": octoprint_camera,
            "offer": "v=0\r\n",
        }
    )
    response = await client.receive_json()
    assert response["id"] == 3
    assert response["type"] == TYPE_RESULT
    assert not response["success"]
