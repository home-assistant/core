"""Test for Nest cameras platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
import datetime as dt
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs, urlsplit

import aiohttp
from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
from google_nest_sdm.event import EventMessage
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator

from homeassistant.components import camera, media_source
from homeassistant.components.camera import (
    Camera,
    CameraState,
    CameraWebRTCProvider,
    StreamType,
    WebRTCSendMessage,
)
from homeassistant.components.nest.camera import (
    SNAPSHOT_CACHE_DURATION,
    SNAPSHOT_MAX_RETRY_INTERVAL,
    SNAPSHOT_MIN_RETRY_INTERVAL,
)
from homeassistant.components.nest.const import CONF_WEBRTC_SNAPSHOTS, DOMAIN
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .common import CLIENT_ID, CLIENT_SECRET, DEVICE_ID, CreateDevice, PlatformSetup
from .conftest import FAKE_REFRESH_TOKEN, FakeAuth

PLATFORM = "camera"
CAMERA_DEVICE_TYPE = "sdm.devices.types.CAMERA"
DEVICE_TRAITS = {
    "sdm.devices.traits.Info": {
        "customName": "My Camera",
    },
    "sdm.devices.traits.CameraLiveStream": {
        "maxVideoResolution": {
            "width": 640,
            "height": 480,
        },
        "videoCodecs": ["H264"],
        "audioCodecs": ["AAC"],
    },
    "sdm.devices.traits.CameraEventImage": {},
    "sdm.devices.traits.CameraMotion": {},
}
DATETIME_FORMAT = "YY-MM-DDTHH:MM:SS"
MOTION_EVENT_ID = "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
EVENT_SESSION_ID = "CjY5Y3VKaTZwR3o4Y19YbTVfMF..."

IMAGE_BYTES_FROM_STREAM = b"test stream image bytes"

TEST_IMAGE_URL = "https://domain/sdm_event_snapshot/dGTZwR3o4Y1..."
GENERATE_IMAGE_URL_RESPONSE = {
    "results": {
        "url": TEST_IMAGE_URL,
        "token": "g.0.eventToken",
    },
}
IMAGE_AUTHORIZATION_HEADERS = {"Authorization": "Basic g.0.eventToken"}


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to set platforms used in the test."""
    return ["camera"]


@pytest.fixture
async def device_type() -> str:
    """Fixture to set default device type used when creating devices."""
    return "sdm.devices.types.CAMERA"


@pytest.fixture
def camera_device(create_device: CreateDevice) -> None:
    """Fixture to create a basic camera device."""
    create_device.create(DEVICE_TRAITS)


@pytest.fixture
def webrtc_camera_device(create_device: CreateDevice) -> None:
    """Fixture to create a WebRTC camera device."""
    create_device.create(
        {
            "sdm.devices.traits.Info": {
                "customName": "My Camera",
            },
            "sdm.devices.traits.CameraLiveStream": {
                "maxVideoResolution": {
                    "width": 640,
                    "height": 480,
                },
                "videoCodecs": ["H264"],
                "audioCodecs": ["AAC"],
                "supportedProtocols": ["WEB_RTC"],
            },
        }
    )


def make_motion_event(
    event_id: str = MOTION_EVENT_ID,
    event_session_id: str = EVENT_SESSION_ID,
    timestamp: dt.datetime | None = None,
) -> EventMessage:
    """Create an EventMessage for a motion event."""
    if not timestamp:
        timestamp = utcnow()
    return EventMessage.create_event(
        {
            # Ignored; we use the resource updated event id below
            "eventId": "some-event-id",
            "timestamp": timestamp.isoformat(timespec="seconds"),
            "resourceUpdate": {
                "name": DEVICE_ID,
                "events": {
                    "sdm.devices.events.CameraMotion.Motion": {
                        "eventSessionId": event_session_id,
                        "eventId": event_id,
                    },
                },
            },
        },
        auth=None,
    )


def make_stream_url_response(
    expiration: dt.datetime | None = None, token_num: int = 0
) -> aiohttp.web.Response:
    """Make response for the API that generates a streaming url."""
    if not expiration:
        # Default to an arbitrary time in the future
        expiration = utcnow() + dt.timedelta(seconds=100)
    return aiohttp.web.json_response(
        {
            "results": {
                "streamUrls": {
                    "rtspUrl": f"rtsp://some/url?auth=g.{token_num}.streamingToken"
                },
                "streamExtensionToken": f"g.{token_num}.extensionToken",
                "streamToken": f"g.{token_num}.streamingToken",
                "expiresAt": expiration.isoformat(timespec="seconds"),
            },
        }
    )


@pytest.fixture
async def mock_create_stream(hass: HomeAssistant) -> Generator[AsyncMock]:
    """Fixture to mock out the create stream call."""
    assert await async_setup_component(hass, "stream", {})
    with patch(
        "homeassistant.components.camera.entity.create_stream", autospec=True
    ) as mock_stream:
        mock_stream.return_value.endpoint_url.return_value = (
            "http://home.assistant/playlist.m3u8"
        )
        mock_stream.return_value.async_get_image = AsyncMock()
        mock_stream.return_value.async_get_image.return_value = IMAGE_BYTES_FROM_STREAM
        mock_stream.return_value.start = AsyncMock()
        yield mock_stream


async def async_get_image(
    hass: HomeAssistant,
    width: int | None = None,
    height: int | None = None,
    expected_content_type: str = "image/jpeg",
) -> bytes:
    """Get the camera image."""
    image = await camera.async_get_image(
        hass, "camera.my_camera", width=width, height=height
    )
    assert image.content_type == expected_content_type
    return image.content


async def async_frontend_stream_types(
    client: MockHAClientWebSocket, entity_id: str
) -> list[str] | None:
    """Get the frontend stream types supported."""
    await client.send_json_auto_id(
        {"type": "camera/capabilities", "entity_id": entity_id}
    )
    msg = await client.receive_json()
    assert msg.get("type") == TYPE_RESULT
    assert msg.get("success")
    assert msg.get("result")
    return msg["result"].get("frontend_stream_types")


async def fire_alarm(hass: HomeAssistant, point_in_time: dt.datetime) -> None:
    """Fire an alarm and wait for callbacks to run."""
    with freeze_time(point_in_time):
        async_fire_time_changed(hass, point_in_time)
        await hass.async_block_till_done()


async def test_no_devices(hass: HomeAssistant, setup_platform: PlatformSetup) -> None:
    """Test configuration that returns no devices."""
    await setup_platform()
    assert len(hass.states.async_all()) == 0


async def test_ineligible_device(
    hass: HomeAssistant, setup_platform: PlatformSetup, create_device: CreateDevice
) -> None:
    """Test configuration with devices that do not support cameras."""
    create_device.create(
        {
            "sdm.devices.traits.Info": {
                "customName": "My Camera",
            },
        }
    )

    await setup_platform()
    assert len(hass.states.async_all()) == 0


async def test_camera_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    setup_platform: PlatformSetup,
    camera_device: None,
) -> None:
    """Test a basic camera with a live stream."""
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    camera = hass.states.get("camera.my_camera")
    assert camera is not None
    assert camera.state == CameraState.STREAMING
    assert camera.attributes.get(ATTR_FRIENDLY_NAME) == "My Camera"

    entry = entity_registry.async_get("camera.my_camera")
    assert entry.unique_id == f"{DEVICE_ID}-camera"
    assert entry.domain == "camera"

    device = device_registry.async_get(entry.device_id)
    assert device.name == "My Camera"
    assert device.model == "Camera"
    assert device.identifiers == {("nest", DEVICE_ID)}


async def test_camera_stream(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    camera_device: None,
    auth: FakeAuth,
    mock_create_stream: Mock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a basic camera and fetch its live stream."""
    auth.responses = [make_stream_url_response()]
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING
    client = await hass_ws_client(hass)
    frontend_stream_types = await async_frontend_stream_types(
        client, "camera.my_camera"
    )
    assert frontend_stream_types == [StreamType.HLS]

    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.0.streamingToken"


async def test_camera_ws_stream(
    hass: HomeAssistant,
    setup_platform,
    camera_device,
    hass_ws_client: WebSocketGenerator,
    auth,
    mock_create_stream,
) -> None:
    """Test a basic camera that supports web rtc."""
    auth.responses = [make_stream_url_response()]
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING
    client = await hass_ws_client(hass)
    frontend_stream_types = await async_frontend_stream_types(
        client, "camera.my_camera"
    )
    assert frontend_stream_types == [StreamType.HLS]

    await client.send_json(
        {
            "id": 2,
            "type": "camera/stream",
            "entity_id": "camera.my_camera",
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 2
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"]["url"] == "http://home.assistant/playlist.m3u8"


async def test_camera_ws_stream_failure(
    hass: HomeAssistant,
    setup_platform,
    camera_device,
    hass_ws_client: WebSocketGenerator,
    auth,
) -> None:
    """Test a basic camera that supports web rtc."""
    auth.responses = [aiohttp.web.Response(status=HTTPStatus.BAD_REQUEST)]
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 3,
            "type": "camera/stream",
            "entity_id": "camera.my_camera",
        }
    )

    msg = await client.receive_json()
    assert msg["id"] == 3
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == "start_stream_failed"
    assert msg["error"]["message"].startswith("Nest API error")


async def test_camera_stream_missing_trait(
    hass: HomeAssistant, setup_platform, create_device
) -> None:
    """Test that cameras missing a live stream are not supported."""
    create_device.create(
        {
            "sdm.devices.traits.Info": {
                "customName": "My Camera",
            },
            "sdm.devices.traits.CameraImage": {
                "maxImageResolution": {
                    "width": 800,
                    "height": 600,
                }
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 0


async def test_refresh_expired_stream_token(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    camera_device: None,
) -> None:
    """Test a camera stream expiration and refresh."""
    now = utcnow()
    stream_1_expiration = now + dt.timedelta(seconds=90)
    stream_2_expiration = now + dt.timedelta(seconds=180)
    stream_3_expiration = now + dt.timedelta(seconds=360)
    auth.responses = [
        # Stream URL #1
        make_stream_url_response(stream_1_expiration, token_num=1),
        # Stream URL #2
        make_stream_url_response(stream_2_expiration, token_num=2),
        # Stream URL #3
        make_stream_url_response(stream_3_expiration, token_num=3),
    ]
    await setup_platform()
    assert await async_setup_component(hass, "stream", {})

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING

    # Request a stream for the camera entity to exercise nest cam + camera interaction
    # and shutdown on url expiration
    with patch("homeassistant.components.camera.entity.create_stream") as create_stream:
        create_stream.return_value.start = AsyncMock()
        hls_url = await camera.async_request_stream(hass, "camera.my_camera", fmt="hls")
        assert hls_url.startswith("/api/hls/")  # Includes access token
        assert create_stream.called

    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.1.streamingToken"

    # Fire alarm before stream_1_expiration. The stream url is not refreshed
    next_update = now + dt.timedelta(seconds=25)
    await fire_alarm(hass, next_update)
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.1.streamingToken"

    # Alarm is near stream_1_expiration which causes the stream extension
    next_update = now + dt.timedelta(seconds=65)
    await fire_alarm(hass, next_update)
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"

    # HLS stream is not re-created, just the source is updated
    with patch("homeassistant.components.camera.entity.create_stream") as create_stream:
        hls_url1 = await camera.async_request_stream(
            hass, "camera.my_camera", fmt="hls"
        )
        assert hls_url == hls_url1

    # Next alarm is well before stream_2_expiration, no change
    next_update = now + dt.timedelta(seconds=100)
    await fire_alarm(hass, next_update)
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"

    # Alarm is near stream_2_expiration, causing it to be extended
    next_update = now + dt.timedelta(seconds=155)
    await fire_alarm(hass, next_update)
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.3.streamingToken"

    # HLS stream is still not re-created
    with patch("homeassistant.components.camera.entity.create_stream") as create_stream:
        hls_url2 = await camera.async_request_stream(
            hass, "camera.my_camera", fmt="hls"
        )
        assert hls_url == hls_url2


async def test_stream_response_already_expired(
    hass: HomeAssistant,
    auth: FakeAuth,
    setup_platform: PlatformSetup,
    camera_device: None,
) -> None:
    """Test a API response returning an expired stream url."""
    now = utcnow()
    stream_1_expiration = now + dt.timedelta(seconds=-90)
    stream_2_expiration = now + dt.timedelta(seconds=+90)
    auth.responses = [
        make_stream_url_response(stream_1_expiration, token_num=1),
        make_stream_url_response(stream_2_expiration, token_num=2),
    ]
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING

    # The stream is expired, but we return it anyway
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.1.streamingToken"

    await fire_alarm(hass, now)

    # Second attempt sees that the stream is expired and refreshes
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"


async def test_extending_stream_already_expired(
    hass: HomeAssistant,
    auth: FakeAuth,
    setup_platform: PlatformSetup,
    camera_device: None,
) -> None:
    """Test a API response when extending the stream returns an expired stream url."""
    now = utcnow()
    stream_1_expiration = now + dt.timedelta(seconds=180)
    stream_2_expiration = now + dt.timedelta(seconds=30)  # Will be in the past
    stream_3_expiration = now + dt.timedelta(seconds=600)
    auth.responses = [
        make_stream_url_response(stream_1_expiration, token_num=1),
        make_stream_url_response(stream_2_expiration, token_num=2),
        make_stream_url_response(stream_3_expiration, token_num=3),
    ]
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING

    # The stream is expired, but we return it anyway
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.1.streamingToken"

    # Jump to when the stream will be refreshed
    await fire_alarm(hass, now + dt.timedelta(seconds=160))
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"

    # The stream will have expired in the past, but 1 minute min
    # refresh interval is applied.
    # The stream token is not updated.
    await fire_alarm(hass, now + dt.timedelta(seconds=170))
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"

    # Now go past the min update interval and the stream is refreshed
    await fire_alarm(hass, now + dt.timedelta(seconds=225))
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.3.streamingToken"


async def test_camera_removed(
    hass: HomeAssistant,
    auth: FakeAuth,
    camera_device: None,
    setup_platform: PlatformSetup,
) -> None:
    """Test case where entities are removed and stream tokens revoked."""
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING

    # Start a stream, exercising cleanup on remove
    auth.responses = [
        make_stream_url_response(),
        aiohttp.web.json_response({"results": {}}),
    ]
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.0.streamingToken"

    for config_entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_camera_remove_failure(
    hass: HomeAssistant,
    auth: FakeAuth,
    camera_device: None,
    setup_platform: PlatformSetup,
) -> None:
    """Test case where revoking the stream token fails on unload."""
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING

    # Start a stream, exercising cleanup on remove
    auth.responses = [
        make_stream_url_response(),
        # Stop command will get a failure response
        aiohttp.web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR),
    ]
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.0.streamingToken"

    # Unload should succeed even if an RPC fails
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_refresh_expired_stream_failure(
    hass: HomeAssistant,
    auth: FakeAuth,
    setup_platform: PlatformSetup,
    camera_device: None,
) -> None:
    """Tests a failure when refreshing the stream."""
    now = utcnow()
    stream_1_expiration = now + dt.timedelta(seconds=90)
    stream_2_expiration = now + dt.timedelta(seconds=180)
    auth.responses = [
        make_stream_url_response(expiration=stream_1_expiration, token_num=1),
        # Extending the stream fails with arbitrary error
        aiohttp.web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR),
        # Next attempt to get a stream fetches a new url
        make_stream_url_response(expiration=stream_2_expiration, token_num=2),
    ]
    await setup_platform()
    assert await async_setup_component(hass, "stream", {})

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING

    # Request an HLS stream
    with patch("homeassistant.components.camera.entity.create_stream") as create_stream:
        create_stream.return_value.start = AsyncMock()
        create_stream.return_value.stop = AsyncMock()
        hls_url = await camera.async_request_stream(hass, "camera.my_camera", fmt="hls")
        assert hls_url.startswith("/api/hls/")  # Includes access token
        assert create_stream.called

    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.1.streamingToken"

    # Fire alarm when stream is nearing expiration, causing it to be extended.
    # The stream expires.
    next_update = now + dt.timedelta(seconds=65)
    await fire_alarm(hass, next_update)

    # The stream is entirely refreshed
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"

    # Requesting an HLS stream will create an entirely new stream
    with patch("homeassistant.components.camera.entity.create_stream") as create_stream:
        create_stream.return_value.start = AsyncMock()
        # The HLS stream endpoint was invalidated, with a new auth token
        hls_url2 = await camera.async_request_stream(
            hass, "camera.my_camera", fmt="hls"
        )
        assert hls_url != hls_url2
        assert hls_url2.startswith("/api/hls/")  # Includes access token
        assert create_stream.called


@pytest.mark.usefixtures("webrtc_camera_device")
async def test_camera_web_rtc(
    hass: HomeAssistant,
    auth,
    hass_ws_client: WebSocketGenerator,
    setup_platform,
) -> None:
    """Test a basic camera that supports web rtc."""
    expiration = utcnow() + dt.timedelta(seconds=100)
    auth.responses = [
        aiohttp.web.json_response(
            {
                "results": {
                    "answerSdp": "v=0\r\ns=-\r\n",
                    "mediaSessionId": "yP2grqz0Y1V_wgiX9KEbMWHoLd...",
                    "expiresAt": expiration.isoformat(timespec="seconds"),
                },
            }
        )
    ]
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING
    client = await hass_ws_client(hass)
    assert await async_frontend_stream_types(client, "camera.my_camera") == [
        StreamType.WEB_RTC
    ]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.my_camera",
            "offer": "a=recvonly",
        }
    )

    response = await client.receive_json()
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "answer",
        "answer": "v=0\r\ns=-\r\n",
    }

    # The WebRTC placeholder is a PNG, served as image/png not the default jpeg.
    png_bytes = await async_get_image(hass, expected_content_type="image/png")
    assert png_bytes.startswith(b"\x89PNG")
    await async_get_image(
        hass, width=1024, height=768, expected_content_type="image/png"
    )


@pytest.mark.usefixtures("auth", "camera_device")
async def test_camera_web_rtc_unsupported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_platform,
) -> None:
    """Test a basic camera that supports web rtc."""
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING

    client = await hass_ws_client(hass)
    assert await async_frontend_stream_types(client, "camera.my_camera") == [
        StreamType.HLS
    ]

    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.my_camera",
            "offer": "a=recvonly",
        }
    )

    msg = await client.receive_json()
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]
    assert msg["error"] == {
        "code": "webrtc_offer_failed",
        "message": (
            "Camera does not support WebRTC,"
            " frontend_stream_types={<StreamType.HLS: 'hls'>}"
        ),
    }


@pytest.mark.usefixtures("webrtc_camera_device")
async def test_camera_web_rtc_offer_failure(
    hass: HomeAssistant,
    auth,
    hass_ws_client: WebSocketGenerator,
    setup_platform,
) -> None:
    """Test a basic camera that supports web rtc."""
    auth.responses = [
        aiohttp.web.Response(status=HTTPStatus.BAD_REQUEST),
    ]
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.my_camera",
            "offer": "a=recvonly",
        }
    )

    response = await client.receive_json()
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "error",
        "code": "webrtc_offer_failed",
        "message": "Nest API error:  response from API (400)",
    }


@pytest.mark.usefixtures("mock_create_stream")
async def test_camera_multiple_streams(
    hass: HomeAssistant,
    auth,
    hass_ws_client: WebSocketGenerator,
    create_device,
    setup_platform,
) -> None:
    """Test a camera supporting multiple stream types."""
    expiration = utcnow() + dt.timedelta(seconds=100)
    auth.responses = [
        # WebRTC response
        aiohttp.web.json_response(
            {
                "results": {
                    "answerSdp": "v=0\r\ns=-\r\n",
                    "mediaSessionId": "yP2grqz0Y1V_wgiX9KEbMWHoLd...",
                    "expiresAt": expiration.isoformat(timespec="seconds"),
                },
            }
        ),
    ]
    create_device.create(
        {
            "sdm.devices.traits.Info": {
                "customName": "My Camera",
            },
            "sdm.devices.traits.CameraLiveStream": {
                "maxVideoResolution": {
                    "width": 640,
                    "height": 480,
                },
                "videoCodecs": ["H264"],
                "audioCodecs": ["AAC"],
                "supportedProtocols": ["WEB_RTC", "RTSP"],
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING
    # Prefer WebRTC over RTSP/HLS
    client = await hass_ws_client(hass)
    assert await async_frontend_stream_types(client, "camera.my_camera") == [
        StreamType.WEB_RTC
    ]

    # RTSP stream is not supported
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert not stream_source

    # WebRTC stream
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.my_camera",
            "offer": "a=recvonly",
        }
    )

    response = await client.receive_json()
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "answer",
        "answer": "v=0\r\ns=-\r\n",
    }


@pytest.mark.usefixtures("webrtc_camera_device")
async def test_webrtc_refresh_expired_stream(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    hass_ws_client: WebSocketGenerator,
    auth: FakeAuth,
) -> None:
    """Test a camera webrtc expiration and refresh."""
    now = utcnow()

    stream_1_expiration = now + dt.timedelta(seconds=90)
    stream_2_expiration = now + dt.timedelta(seconds=180)
    auth.responses = [
        aiohttp.web.json_response(
            {
                "results": {
                    "answerSdp": "v=0\r\ns=-\r\n",
                    "mediaSessionId": "yP2grqz0Y1V_wgiX9KEbMWHoLd...",
                    "expiresAt": stream_1_expiration.isoformat(timespec="seconds"),
                },
            }
        ),
        aiohttp.web.json_response(
            {
                "results": {
                    "mediaSessionId": "yP2grqz0Y1V_wgiX9KEbMWHoLd...",
                    "expiresAt": stream_2_expiration.isoformat(timespec="seconds"),
                },
            }
        ),
    ]
    await setup_platform()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == CameraState.STREAMING
    client = await hass_ws_client(hass)
    assert await async_frontend_stream_types(client, "camera.my_camera") == [
        StreamType.WEB_RTC
    ]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.my_camera",
            "offer": "a=recvonly",
        }
    )

    response = await client.receive_json()
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "answer",
        "answer": "v=0\r\ns=-\r\n",
    }

    assert len(auth.captured_requests) == 1
    assert (
        auth.captured_requests[0][2].get("command")
        == "sdm.devices.commands.CameraLiveStream.GenerateWebRtcStream"
    )

    # Fire alarm before stream_1_expiration. The stream url is not refreshed
    next_update = now + dt.timedelta(seconds=25)
    await fire_alarm(hass, next_update)
    assert len(auth.captured_requests) == 1

    # Alarm is near stream_1_expiration which causes the stream extension
    next_update = now + dt.timedelta(seconds=60)
    await fire_alarm(hass, next_update)

    assert len(auth.captured_requests) >= 2
    assert (
        auth.captured_requests[1][2].get("command")
        == "sdm.devices.commands.CameraLiveStream.ExtendWebRtcStream"
    )


@pytest.mark.usefixtures("webrtc_camera_device")
async def test_webrtc_refresh_failed_precondition(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    hass_ws_client: WebSocketGenerator,
    auth: FakeAuth,
) -> None:
    """Test a WebRTC stream that can't be extended is not refreshed again."""
    now = utcnow()
    auth.responses = [
        aiohttp.web.json_response(
            {
                "results": {
                    "answerSdp": "v=0\r\ns=-\r\n",
                    "mediaSessionId": "yP2grqz0Y1V_wgiX9KEbMWHoLd...",
                    "expiresAt": (now + dt.timedelta(seconds=90)).isoformat(
                        timespec="seconds"
                    ),
                },
            }
        ),
        aiohttp.web.json_response(
            {
                "error": {
                    "code": 400,
                    "message": (
                        "WebRtc error caused by invalid session or user id mismatch."
                    ),
                    "status": "FAILED_PRECONDITION",
                }
            },
            status=HTTPStatus.BAD_REQUEST,
        ),
    ]
    await setup_platform()
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.my_camera",
            "offer": "a=recvonly",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    # The stream extension fails because the session is no longer valid
    await fire_alarm(hass, now + dt.timedelta(seconds=60))
    # Retrying the extension can't succeed, so it is not attempted again
    await fire_alarm(hass, now + dt.timedelta(minutes=10))
    await fire_alarm(hass, now + dt.timedelta(hours=1))

    extend_requests = [
        request
        for request in auth.captured_requests
        if request[2].get("command")
        == "sdm.devices.commands.CameraLiveStream.ExtendWebRtcStream"
    ]
    assert len(extend_requests) == 1


SNAPSHOT_BYTES = b"\xff\xd8 test snapshot jpeg"
SNAPSHOT_OPTIONS = pytest.mark.parametrize(
    "config_entry_options", [{CONF_WEBRTC_SNAPSHOTS: True}], ids=["snapshots"]
)


class FakeSnapshotProvider(CameraWebRTCProvider):
    """WebRTC provider that returns still images for `nest:` stream sources."""

    def __init__(self) -> None:
        """Initialize the provider."""
        self.stream_sources: list[str] = []
        self.async_get_image = AsyncMock(return_value=SNAPSHOT_BYTES)
        self.unregister: Callable[[], None] | None = None

    @property
    def domain(self) -> str:
        """Return the provider domain."""
        return "fake_provider"

    @callback
    def async_is_supported(self, stream_source: str) -> bool:
        """Support `nest:` stream sources only."""
        self.stream_sources.append(stream_source)
        return stream_source.startswith("nest:")

    async def async_handle_async_webrtc_offer(
        self,
        camera: Camera,
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
    ) -> None:
        """Not used, the Nest camera handles offers itself."""
        raise NotImplementedError

    async def async_on_webrtc_candidate(self, session_id: str, candidate: Any) -> None:
        """Not used, the Nest camera handles candidates itself."""
        raise NotImplementedError


@pytest.fixture
async def snapshot_provider(
    hass: HomeAssistant,
) -> AsyncGenerator[FakeSnapshotProvider]:
    """Register a WebRTC provider that can fetch stills."""
    assert await async_setup_component(hass, camera.DOMAIN, {})
    provider = FakeSnapshotProvider()
    provider.unregister = camera.async_register_webrtc_provider(hass, provider)
    await hass.async_block_till_done()
    yield provider
    if provider.unregister is not None:
        provider.unregister()


def get_camera(hass: HomeAssistant) -> Camera:
    """Return the camera entity object."""
    return hass.data[camera.DATA_COMPONENT].get_entity("camera.my_camera")


def hanging_image(started: asyncio.Event, release: asyncio.Event, image: bytes):
    """Return a side effect that blocks until released."""

    async def get_image(*args: Any, **kwargs: Any) -> bytes:
        started.set()
        await release.wait()
        return image

    return get_image


@pytest.mark.usefixtures("webrtc_camera_device")
async def test_webrtc_snapshots_disabled(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    snapshot_provider: FakeSnapshotProvider,
) -> None:
    """Test a WebRTC camera serves the placeholder when snapshots are disabled."""
    await setup_platform()

    cam = get_camera(hass)
    assert await cam.async_webrtc_provider_stream_source() is None
    assert cam.webrtc_provider is None
    assert snapshot_provider.stream_sources == []

    png_bytes = await async_get_image(hass, expected_content_type="image/png")
    assert png_bytes.startswith(b"\x89PNG")
    snapshot_provider.async_get_image.assert_not_called()


@pytest.mark.usefixtures("webrtc_camera_device")
@SNAPSHOT_OPTIONS
async def test_webrtc_snapshots(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    snapshot_provider: FakeSnapshotProvider,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a WebRTC camera fetches stills from the provider and caches them."""
    await setup_platform()

    cam = get_camera(hass)
    assert cam.webrtc_provider is snapshot_provider
    assert cam.content_type == "image/jpeg"

    source = urlsplit(snapshot_provider.stream_sources[-1])
    assert source.scheme == "nest"
    assert parse_qs(source.query) == {
        "client_id": [CLIENT_ID],
        "client_secret": [CLIENT_SECRET],
        "refresh_token": [FAKE_REFRESH_TOKEN],
        "project_id": ["project-id"],
        "device_id": ["device-id"],
        "protocols": ["WEB_RTC"],
    }

    # The source is only for the provider. Live view is still handled natively,
    # and the stream component and media browser don't see the camera.
    assert await cam.stream_source() is None
    client = await hass_ws_client(hass)
    assert await async_frontend_stream_types(client, "camera.my_camera") == [
        StreamType.WEB_RTC
    ]
    with pytest.raises(HomeAssistantError, match="does not support streaming"):
        await camera.async_request_stream(hass, "camera.my_camera", "hls")
    assert await async_setup_component(hass, "media_source", {})
    browse = await media_source.async_browse_media(hass, "media-source://camera")
    assert browse.children == []

    assert await async_get_image(hass) == SNAPSHOT_BYTES
    snapshot_provider.async_get_image.assert_called_once_with(cam)

    # A request within the cache duration reuses the image, also when scaled,
    # as the image is always fetched at full size
    freezer.tick(SNAPSHOT_CACHE_DURATION - dt.timedelta(seconds=1))
    with patch(
        "homeassistant.components.camera.scale_jpeg_camera_image",
        return_value=b"scaled",
    ) as scale:
        assert await async_get_image(hass, width=320, height=240) == b"scaled"
    scale.assert_called_once()
    assert scale.call_args[0][0].content == SNAPSHOT_BYTES
    assert snapshot_provider.async_get_image.call_count == 1

    # Once it expires, a new image is fetched
    freezer.tick(dt.timedelta(seconds=1))
    snapshot_provider.async_get_image.return_value = b"\xff\xd8 new"
    assert await async_get_image(hass) == b"\xff\xd8 new"
    assert snapshot_provider.async_get_image.call_count == 2


@pytest.mark.usefixtures("webrtc_camera_device")
@SNAPSHOT_OPTIONS
async def test_webrtc_snapshots_concurrent_requests(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    snapshot_provider: FakeSnapshotProvider,
) -> None:
    """Test concurrent still requests share a single fetch."""
    await setup_platform()

    started = asyncio.Event()
    release = asyncio.Event()
    snapshot_provider.async_get_image.side_effect = hanging_image(
        started, release, SNAPSHOT_BYTES
    )
    first = asyncio.create_task(async_get_image(hass))
    await started.wait()
    others = [asyncio.create_task(async_get_image(hass)) for _ in range(2)]
    await asyncio.sleep(0)
    release.set()
    assert await asyncio.gather(first, *others) == [SNAPSHOT_BYTES] * 3
    assert snapshot_provider.async_get_image.call_count == 1


@pytest.mark.usefixtures("webrtc_camera_device")
@SNAPSHOT_OPTIONS
@pytest.mark.parametrize(
    "image_side_effect",
    [HomeAssistantError("Unable to get image from go2rtc"), [None], [b""]],
    ids=["error", "no_image", "empty_image"],
)
async def test_webrtc_snapshots_failure(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    snapshot_provider: FakeSnapshotProvider,
    freezer: FrozenDateTimeFactory,
    image_side_effect: Exception | list[bytes | None],
) -> None:
    """Test a failed fetch has no image, and is retried after a short interval."""
    await setup_platform()

    snapshot_provider.async_get_image.side_effect = image_side_effect
    with pytest.raises(HomeAssistantError, match="Unable to get image"):
        await async_get_image(hass)
    freezer.tick(SNAPSHOT_MIN_RETRY_INTERVAL - dt.timedelta(seconds=1))
    with pytest.raises(HomeAssistantError, match="Unable to get image"):
        await async_get_image(hass)
    assert snapshot_provider.async_get_image.call_count == 1

    freezer.tick(dt.timedelta(seconds=1))
    snapshot_provider.async_get_image.side_effect = None
    assert await async_get_image(hass) == SNAPSHOT_BYTES
    assert snapshot_provider.async_get_image.call_count == 2


@pytest.mark.usefixtures("webrtc_camera_device")
@SNAPSHOT_OPTIONS
async def test_webrtc_snapshots_failure_backoff(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    snapshot_provider: FakeSnapshotProvider,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the wait after a failed fetch doubles up to a maximum, until a success."""
    await setup_platform()
    snapshot_provider.async_get_image.return_value = None

    async def attempts_after(wait: dt.timedelta) -> int:
        """Return the fetch count after waiting, with no fetch just before."""
        count = snapshot_provider.async_get_image.call_count
        freezer.tick(wait - dt.timedelta(seconds=1))
        with pytest.raises(HomeAssistantError, match="Unable to get image"):
            await async_get_image(hass)
        assert snapshot_provider.async_get_image.call_count == count
        freezer.tick(dt.timedelta(seconds=1))
        with pytest.raises(HomeAssistantError, match="Unable to get image"):
            await async_get_image(hass)
        return snapshot_provider.async_get_image.call_count

    with pytest.raises(HomeAssistantError, match="Unable to get image"):
        await async_get_image(hass)
    assert snapshot_provider.async_get_image.call_count == 1
    wait = SNAPSHOT_MIN_RETRY_INTERVAL
    for count in range(2, 8):
        assert await attempts_after(wait) == count
        wait = min(wait * 2, SNAPSHOT_MAX_RETRY_INTERVAL)
    assert wait == SNAPSHOT_MAX_RETRY_INTERVAL

    # A success resets the wait for the next failure
    snapshot_provider.async_get_image.return_value = SNAPSHOT_BYTES
    freezer.tick(wait)
    assert await async_get_image(hass) == SNAPSHOT_BYTES
    snapshot_provider.async_get_image.return_value = None
    freezer.tick(SNAPSHOT_CACHE_DURATION)
    with pytest.raises(HomeAssistantError, match="Unable to get image"):
        await async_get_image(hass)
    assert await attempts_after(SNAPSHOT_MIN_RETRY_INTERVAL) == 10


@pytest.mark.usefixtures("webrtc_camera_device")
@SNAPSHOT_OPTIONS
async def test_webrtc_snapshots_caller_timeout(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    snapshot_provider: FakeSnapshotProvider,
) -> None:
    """Test a caller timing out doesn't cancel the fetch or serve a stale image."""
    await setup_platform()
    # The cached image expires at once, and the next fetch is slower than the
    # caller
    with patch(
        "homeassistant.components.nest.camera.SNAPSHOT_CACHE_DURATION",
        dt.timedelta(0),
    ):
        assert await async_get_image(hass) == SNAPSHOT_BYTES
    started = asyncio.Event()
    release = asyncio.Event()
    snapshot_provider.async_get_image.side_effect = hanging_image(
        started, release, b"\xff\xd8 new"
    )
    with pytest.raises(HomeAssistantError, match="Unable to get image"):
        await camera.async_get_image(hass, "camera.my_camera", timeout=0.01)
    assert started.is_set()

    # The fetch carries on and fills the cache for the next request
    release.set()
    await hass.async_block_till_done()
    assert await async_get_image(hass) == b"\xff\xd8 new"
    assert snapshot_provider.async_get_image.call_count == 2


@pytest.mark.usefixtures("webrtc_camera_device")
@SNAPSHOT_OPTIONS
async def test_webrtc_snapshots_fetch_timeout(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    snapshot_provider: FakeSnapshotProvider,
) -> None:
    """Test a fetch that never finishes is given up on."""
    await setup_platform()

    started = asyncio.Event()
    snapshot_provider.async_get_image.side_effect = hanging_image(
        started, asyncio.Event(), SNAPSHOT_BYTES
    )
    with (
        patch("homeassistant.components.nest.camera.SNAPSHOT_FETCH_TIMEOUT", 0.01),
        pytest.raises(HomeAssistantError, match="Unable to get image"),
    ):
        await async_get_image(hass)
    assert started.is_set()
    task = get_camera(hass)._snapshot_task
    assert task is not None
    assert task.done()


@pytest.mark.usefixtures("webrtc_camera_device")
@SNAPSHOT_OPTIONS
async def test_webrtc_snapshots_without_provider(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test there is no image, and a warning once, when no provider is set up."""
    await setup_platform()

    cam = get_camera(hass)
    assert (await cam.async_webrtc_provider_stream_source() or "").startswith("nest:?")
    assert cam.webrtc_provider is None
    for _ in range(2):
        with pytest.raises(HomeAssistantError, match="Unable to get image"):
            await async_get_image(hass)
    assert caplog.text.count("need a WebRTC provider that supports Nest") == 1


@pytest.mark.usefixtures("webrtc_camera_device")
@SNAPSHOT_OPTIONS
async def test_webrtc_snapshots_unexpected_device_name(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
) -> None:
    """Test there is no provider source for a device name in another format."""
    await setup_platform()

    cam = get_camera(hass)
    with patch.object(cam, "_device", Mock()) as device:
        device.name = "devices/device-id"
        assert await cam.async_webrtc_provider_stream_source() is None


@pytest.mark.usefixtures("webrtc_camera_device")
@SNAPSHOT_OPTIONS
async def test_webrtc_snapshots_provider_removed(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    snapshot_provider: FakeSnapshotProvider,
) -> None:
    """Test snapshots stop when the provider is removed at runtime."""
    await setup_platform()
    assert await async_get_image(hass) == SNAPSHOT_BYTES

    assert snapshot_provider.unregister is not None
    snapshot_provider.unregister()
    snapshot_provider.unregister = None
    await hass.async_block_till_done()
    cam = get_camera(hass)
    assert cam.webrtc_provider is None
    with pytest.raises(HomeAssistantError, match="Unable to get image"):
        await async_get_image(hass)
    assert snapshot_provider.async_get_image.call_count == 1


@pytest.mark.usefixtures("webrtc_camera_device")
@SNAPSHOT_OPTIONS
async def test_webrtc_snapshots_fetch_cancelled_on_unload(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    snapshot_provider: FakeSnapshotProvider,
    config_entry: MockConfigEntry,
) -> None:
    """Test a running fetch is cancelled when the config entry is unloaded."""
    await setup_platform()

    started = asyncio.Event()
    snapshot_provider.async_get_image.side_effect = hanging_image(
        started, asyncio.Event(), SNAPSHOT_BYTES
    )
    request = asyncio.create_task(async_get_image(hass))
    await started.wait()
    task = get_camera(hass)._snapshot_task
    assert task is not None

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert task.cancelled()
    # The waiting request wasn't cancelled itself, so it gets no image rather
    # than the fetch's cancellation
    with pytest.raises(HomeAssistantError, match="Unable to get image"):
        await request
