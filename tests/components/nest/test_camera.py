"""Test for Nest cameras platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

from collections.abc import Generator
import datetime
from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
from freezegun import freeze_time
from google_nest_sdm.event import EventMessage
import pytest

from homeassistant.components import camera
from homeassistant.components.camera import CameraState, StreamType
from homeassistant.components.nest.const import DOMAIN
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .common import DEVICE_ID, CreateDevice, FakeSubscriber, PlatformSetup
from .conftest import FakeAuth

from tests.common import async_fire_time_changed
from tests.typing import MockHAClientWebSocket, WebSocketGenerator

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
    timestamp: datetime.datetime | None = None,
) -> EventMessage:
    """Create an EventMessage for a motion event."""
    if not timestamp:
        timestamp = utcnow()
    return EventMessage.create_event(
        {
            "eventId": "some-event-id",  # Ignored; we use the resource updated event id below
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
    expiration: datetime.datetime | None = None, token_num: int = 0
) -> aiohttp.web.Response:
    """Make response for the API that generates a streaming url."""
    if not expiration:
        # Default to an arbitrary time in the future
        expiration = utcnow() + datetime.timedelta(seconds=100)
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
        "homeassistant.components.camera.create_stream", autospec=True
    ) as mock_stream:
        mock_stream.return_value.endpoint_url.return_value = (
            "http://home.assistant/playlist.m3u8"
        )
        mock_stream.return_value.async_get_image = AsyncMock()
        mock_stream.return_value.async_get_image.return_value = IMAGE_BYTES_FROM_STREAM
        mock_stream.return_value.start = AsyncMock()
        yield mock_stream


async def async_get_image(
    hass: HomeAssistant, width: int | None = None, height: int | None = None
) -> bytes:
    """Get the camera image."""
    image = await camera.async_get_image(
        hass, "camera.my_camera", width=width, height=height
    )
    assert image.content_type == "image/jpeg"
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


async def fire_alarm(hass: HomeAssistant, point_in_time: datetime.datetime) -> None:
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
    stream_1_expiration = now + datetime.timedelta(seconds=90)
    stream_2_expiration = now + datetime.timedelta(seconds=180)
    stream_3_expiration = now + datetime.timedelta(seconds=360)
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
    with patch("homeassistant.components.camera.create_stream") as create_stream:
        create_stream.return_value.start = AsyncMock()
        hls_url = await camera.async_request_stream(hass, "camera.my_camera", fmt="hls")
        assert hls_url.startswith("/api/hls/")  # Includes access token
        assert create_stream.called

    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.1.streamingToken"

    # Fire alarm before stream_1_expiration. The stream url is not refreshed
    next_update = now + datetime.timedelta(seconds=25)
    await fire_alarm(hass, next_update)
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.1.streamingToken"

    # Alarm is near stream_1_expiration which causes the stream extension
    next_update = now + datetime.timedelta(seconds=65)
    await fire_alarm(hass, next_update)
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"

    # HLS stream is not re-created, just the source is updated
    with patch("homeassistant.components.camera.create_stream") as create_stream:
        hls_url1 = await camera.async_request_stream(
            hass, "camera.my_camera", fmt="hls"
        )
        assert hls_url == hls_url1

    # Next alarm is well before stream_2_expiration, no change
    next_update = now + datetime.timedelta(seconds=100)
    await fire_alarm(hass, next_update)
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"

    # Alarm is near stream_2_expiration, causing it to be extended
    next_update = now + datetime.timedelta(seconds=155)
    await fire_alarm(hass, next_update)
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.3.streamingToken"

    # HLS stream is still not re-created
    with patch("homeassistant.components.camera.create_stream") as create_stream:
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
    stream_1_expiration = now + datetime.timedelta(seconds=-90)
    stream_2_expiration = now + datetime.timedelta(seconds=+90)
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
    stream_1_expiration = now + datetime.timedelta(seconds=180)
    stream_2_expiration = now + datetime.timedelta(seconds=30)  # Will be in the past
    stream_3_expiration = now + datetime.timedelta(seconds=600)
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
    await fire_alarm(hass, now + datetime.timedelta(seconds=160))
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"

    # The stream will have expired in the past, but 1 minute min refresh interval is applied.
    # The stream token is not updated.
    await fire_alarm(hass, now + datetime.timedelta(seconds=170))
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"

    # Now go past the min update interval and the stream is refreshed
    await fire_alarm(hass, now + datetime.timedelta(seconds=225))
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.3.streamingToken"


async def test_camera_removed(
    hass: HomeAssistant,
    auth: FakeAuth,
    camera_device: None,
    subscriber: FakeSubscriber,
    setup_platform: PlatformSetup,
) -> None:
    """Test case where entities are removed and stream tokens revoked."""
    await setup_platform()
    # Simplify test setup
    subscriber.cache_policy.fetch = False

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
    stream_1_expiration = now + datetime.timedelta(seconds=90)
    stream_2_expiration = now + datetime.timedelta(seconds=180)
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
    with patch("homeassistant.components.camera.create_stream") as create_stream:
        create_stream.return_value.start = AsyncMock()
        create_stream.return_value.stop = AsyncMock()
        hls_url = await camera.async_request_stream(hass, "camera.my_camera", fmt="hls")
        assert hls_url.startswith("/api/hls/")  # Includes access token
        assert create_stream.called

    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.1.streamingToken"

    # Fire alarm when stream is nearing expiration, causing it to be extended.
    # The stream expires.
    next_update = now + datetime.timedelta(seconds=65)
    await fire_alarm(hass, next_update)

    # The stream is entirely refreshed
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"

    # Requesting an HLS stream will create an entirely new stream
    with patch("homeassistant.components.camera.create_stream") as create_stream:
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
    expiration = utcnow() + datetime.timedelta(seconds=100)
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

    # Nest WebRTC cameras return a placeholder
    await async_get_image(hass)
    await async_get_image(hass, width=1024, height=768)


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
        "message": "Camera does not support WebRTC, frontend_stream_types={<StreamType.HLS: 'hls'>}",
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
        "message": "Nest API error: Bad Request response from API (400)",
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
    expiration = utcnow() + datetime.timedelta(seconds=100)
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
    assert cam.attributes["frontend_stream_type"] == StreamType.WEB_RTC
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

    stream_1_expiration = now + datetime.timedelta(seconds=90)
    stream_2_expiration = now + datetime.timedelta(seconds=180)
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
    assert cam.attributes["frontend_stream_type"] == StreamType.WEB_RTC
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
    next_update = now + datetime.timedelta(seconds=25)
    await fire_alarm(hass, next_update)
    assert len(auth.captured_requests) == 1

    # Alarm is near stream_1_expiration which causes the stream extension
    next_update = now + datetime.timedelta(seconds=60)
    await fire_alarm(hass, next_update)

    assert len(auth.captured_requests) >= 2
    assert (
        auth.captured_requests[1][2].get("command")
        == "sdm.devices.commands.CameraLiveStream.ExtendWebRtcStream"
    )
