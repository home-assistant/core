"""
Test for Nest cameras platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

import datetime
from http import HTTPStatus
from unittest.mock import patch

import aiohttp
from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage
import pytest

from homeassistant.components import camera
from homeassistant.components.camera import (
    STATE_IDLE,
    STATE_STREAMING,
    STREAM_TYPE_HLS,
    STREAM_TYPE_WEB_RTC,
)
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .common import async_setup_sdm_platform

from tests.common import async_fire_time_changed

PLATFORM = "camera"
CAMERA_DEVICE_TYPE = "sdm.devices.types.CAMERA"
DEVICE_ID = "some-device-id"
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
DOMAIN = "nest"
MOTION_EVENT_ID = "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
EVENT_SESSION_ID = "CjY5Y3VKaTZwR3o4Y19YbTVfMF..."

# Tests can assert that image bytes came from an event or was decoded
# from the live stream.
IMAGE_BYTES_FROM_EVENT = b"test url image bytes"
IMAGE_BYTES_FROM_STREAM = b"test stream image bytes"

TEST_IMAGE_URL = "https://domain/sdm_event_snapshot/dGTZwR3o4Y1..."
GENERATE_IMAGE_URL_RESPONSE = {
    "results": {
        "url": TEST_IMAGE_URL,
        "token": "g.0.eventToken",
    },
}
IMAGE_AUTHORIZATION_HEADERS = {"Authorization": "Basic g.0.eventToken"}


def make_motion_event(
    event_id: str = MOTION_EVENT_ID,
    event_session_id: str = EVENT_SESSION_ID,
    timestamp: datetime.datetime = None,
) -> EventMessage:
    """Create an EventMessage for a motion event."""
    if not timestamp:
        timestamp = utcnow()
    return EventMessage(
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
    expiration: datetime.datetime = None, token_num: int = 0
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


async def async_setup_camera(hass, traits={}, auth=None):
    """Set up the platform and prerequisites."""
    devices = {}
    if traits:
        devices[DEVICE_ID] = Device.MakeDevice(
            {
                "name": DEVICE_ID,
                "type": CAMERA_DEVICE_TYPE,
                "traits": traits,
            },
            auth=auth,
        )
    return await async_setup_sdm_platform(hass, PLATFORM, devices)


async def fire_alarm(hass, point_in_time):
    """Fire an alarm and wait for callbacks to run."""
    with patch("homeassistant.util.dt.utcnow", return_value=point_in_time):
        async_fire_time_changed(hass, point_in_time)
        await hass.async_block_till_done()


async def async_get_image(hass, width=None, height=None):
    """Get image from the camera, a wrapper around camera.async_get_image."""
    # Note: this patches ImageFrame to simulate decoding an image from a live
    # stream, however the test may not use it. Tests assert on the image
    # contents to determine if the image came from the live stream or event.
    with patch(
        "homeassistant.components.ffmpeg.ImageFrame.get_image",
        autopatch=True,
        return_value=IMAGE_BYTES_FROM_STREAM,
    ):
        return await camera.async_get_image(
            hass, "camera.my_camera", width=width, height=height
        )


async def test_no_devices(hass):
    """Test configuration that returns no devices."""
    await async_setup_camera(hass)
    assert len(hass.states.async_all()) == 0


async def test_ineligible_device(hass):
    """Test configuration with devices that do not support cameras."""
    await async_setup_camera(
        hass,
        {
            "sdm.devices.traits.Info": {
                "customName": "My Camera",
            },
        },
    )
    assert len(hass.states.async_all()) == 0


async def test_camera_device(hass):
    """Test a basic camera with a live stream."""
    await async_setup_camera(hass, DEVICE_TRAITS)

    assert len(hass.states.async_all()) == 1
    camera = hass.states.get("camera.my_camera")
    assert camera is not None
    assert camera.state == STATE_STREAMING

    registry = er.async_get(hass)
    entry = registry.async_get("camera.my_camera")
    assert entry.unique_id == "some-device-id-camera"
    assert entry.original_name == "My Camera"
    assert entry.domain == "camera"

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entry.device_id)
    assert device.name == "My Camera"
    assert device.model == "Camera"
    assert device.identifiers == {("nest", DEVICE_ID)}


async def test_camera_stream(hass, auth):
    """Test a basic camera and fetch its live stream."""
    auth.responses = [make_stream_url_response()]
    await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_STREAMING
    assert cam.attributes["frontend_stream_type"] == STREAM_TYPE_HLS

    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.0.streamingToken"

    image = await async_get_image(hass)
    assert image.content == IMAGE_BYTES_FROM_STREAM


async def test_camera_ws_stream(hass, auth, hass_ws_client):
    """Test a basic camera that supports web rtc."""
    auth.responses = [make_stream_url_response()]
    await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_STREAMING
    assert cam.attributes["frontend_stream_type"] == STREAM_TYPE_HLS

    with patch("homeassistant.components.camera.create_stream") as mock_stream:
        mock_stream().endpoint_url.return_value = "http://home.assistant/playlist.m3u8"
        client = await hass_ws_client(hass)
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


async def test_camera_ws_stream_failure(hass, auth, hass_ws_client):
    """Test a basic camera that supports web rtc."""
    auth.responses = [aiohttp.web.Response(status=HTTPStatus.BAD_REQUEST)]
    await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_STREAMING

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


async def test_camera_stream_missing_trait(hass, auth):
    """Test fetching a video stream when not supported by the API."""
    traits = {
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

    await async_setup_camera(hass, traits, auth=auth)

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_IDLE

    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source is None

    # Unable to get an image from the live stream
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass)


async def test_refresh_expired_stream_token(hass, auth):
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
    await async_setup_camera(
        hass,
        DEVICE_TRAITS,
        auth=auth,
    )
    assert await async_setup_component(hass, "stream", {})

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_STREAMING

    # Request a stream for the camera entity to exercise nest cam + camera interaction
    # and shutdown on url expiration
    with patch("homeassistant.components.camera.create_stream") as create_stream:
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


async def test_stream_response_already_expired(hass, auth):
    """Test a API response returning an expired stream url."""
    now = utcnow()
    stream_1_expiration = now + datetime.timedelta(seconds=-90)
    stream_2_expiration = now + datetime.timedelta(seconds=+90)
    auth.responses = [
        make_stream_url_response(stream_1_expiration, token_num=1),
        make_stream_url_response(stream_2_expiration, token_num=2),
    ]
    await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_STREAMING

    # The stream is expired, but we return it anyway
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.1.streamingToken"

    await fire_alarm(hass, now)

    # Second attempt sees that the stream is expired and refreshes
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"


async def test_camera_removed(hass, auth):
    """Test case where entities are removed and stream tokens revoked."""
    subscriber = await async_setup_camera(
        hass,
        DEVICE_TRAITS,
        auth=auth,
    )
    # Simplify test setup
    subscriber.cache_policy.fetch = False

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_STREAMING

    # Start a stream, exercising cleanup on remove
    auth.responses = [
        make_stream_url_response(),
        aiohttp.web.json_response({"results": {}}),
    ]
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.0.streamingToken"

    # Fetch an event image, exercising cleanup on remove
    await subscriber.async_receive_event(make_motion_event())
    await hass.async_block_till_done()
    auth.responses = [
        aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
    ]
    image = await async_get_image(hass)
    assert image.content == IMAGE_BYTES_FROM_EVENT

    for config_entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_camera_remove_failure(hass, auth):
    """Test case where revoking the stream token fails on unload."""
    await async_setup_camera(
        hass,
        DEVICE_TRAITS,
        auth=auth,
    )

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_STREAMING

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


async def test_refresh_expired_stream_failure(hass, auth):
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
    await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)
    assert await async_setup_component(hass, "stream", {})

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_STREAMING

    # Request an HLS stream
    with patch("homeassistant.components.camera.create_stream") as create_stream:

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
        # The HLS stream endpoint was invalidated, with a new auth token
        hls_url2 = await camera.async_request_stream(
            hass, "camera.my_camera", fmt="hls"
        )
        assert hls_url != hls_url2
        assert hls_url2.startswith("/api/hls/")  # Includes access token
        assert create_stream.called


async def test_camera_image_from_last_event(hass, auth):
    """Test an image generated from an event."""
    # The subscriber receives a message related to an image event. The camera
    # holds on to the event message. When the test asks for a capera snapshot
    # it exchanges the event id for an image url and fetches the image.
    subscriber = await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("camera.my_camera")

    # Simulate a pubsub message received by the subscriber with a motion event.
    await subscriber.async_receive_event(make_motion_event())
    await hass.async_block_till_done()

    auth.responses = [
        # Fake response from API that returns url image
        aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
        # Fake response for the image content fetch
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
    ]

    image = await async_get_image(hass)
    assert image.content == IMAGE_BYTES_FROM_EVENT
    # Verify expected image fetch request was captured
    assert auth.url == TEST_IMAGE_URL
    assert auth.headers == IMAGE_AUTHORIZATION_HEADERS

    # An additional fetch uses the cache and does not send another RPC
    image = await async_get_image(hass)
    assert image.content == IMAGE_BYTES_FROM_EVENT
    # Verify expected image fetch request was captured
    assert auth.url == TEST_IMAGE_URL
    assert auth.headers == IMAGE_AUTHORIZATION_HEADERS


async def test_camera_image_from_event_not_supported(hass, auth):
    """Test fallback to stream image when event images are not supported."""
    # Create a device that does not support the CameraEventImgae trait
    traits = DEVICE_TRAITS.copy()
    del traits["sdm.devices.traits.CameraEventImage"]
    subscriber = await async_setup_camera(hass, traits, auth=auth)
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("camera.my_camera")

    await subscriber.async_receive_event(make_motion_event())
    await hass.async_block_till_done()

    # Camera fetches a stream url since CameraEventImage is not supported
    auth.responses = [make_stream_url_response()]

    image = await async_get_image(hass)
    assert image.content == IMAGE_BYTES_FROM_STREAM


async def test_generate_event_image_url_failure(hass, auth):
    """Test fallback to stream on failure to create an image url."""
    subscriber = await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("camera.my_camera")

    await subscriber.async_receive_event(make_motion_event())
    await hass.async_block_till_done()

    auth.responses = [
        # Fail to generate the image url
        aiohttp.web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR),
        # Camera fetches a stream url as a fallback
        make_stream_url_response(),
    ]

    image = await async_get_image(hass)
    assert image.content == IMAGE_BYTES_FROM_STREAM


async def test_fetch_event_image_failure(hass, auth):
    """Test fallback to a stream on image download failure."""
    subscriber = await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("camera.my_camera")

    await subscriber.async_receive_event(make_motion_event())
    await hass.async_block_till_done()

    auth.responses = [
        # Fake response from API that returns url image
        aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
        # Fail to download the image
        aiohttp.web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR),
        # Camera fetches a stream url as a fallback
        make_stream_url_response(),
    ]

    image = await async_get_image(hass)
    assert image.content == IMAGE_BYTES_FROM_STREAM


async def test_event_image_expired(hass, auth):
    """Test fallback for an event event image that has expired."""
    subscriber = await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("camera.my_camera")

    # Simulate a pubsub message has already expired
    event_timestamp = utcnow() - datetime.timedelta(seconds=40)
    await subscriber.async_receive_event(make_motion_event(timestamp=event_timestamp))
    await hass.async_block_till_done()

    # Fallback to a stream url since the event message is expired.
    auth.responses = [make_stream_url_response()]

    image = await async_get_image(hass)
    assert image.content == IMAGE_BYTES_FROM_STREAM


async def test_multiple_event_images(hass, auth):
    """Test fallback for an event event image that has been cleaned up on expiration."""
    subscriber = await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)
    # Simplify test setup
    subscriber.cache_policy.fetch = False
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("camera.my_camera")

    event_timestamp = utcnow()
    await subscriber.async_receive_event(
        make_motion_event(event_session_id="event-session-1", timestamp=event_timestamp)
    )
    await hass.async_block_till_done()

    auth.responses = [
        # Fake response from API that returns url image
        aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
        # Fake response for the image content fetch
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
        # Image is refetched after being cleared by expiration alarm
        aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
        aiohttp.web.Response(body=b"updated image bytes"),
    ]

    image = await async_get_image(hass)
    assert image.content == IMAGE_BYTES_FROM_EVENT

    next_event_timestamp = event_timestamp + datetime.timedelta(seconds=25)
    await subscriber.async_receive_event(
        make_motion_event(
            event_id="updated-event-id",
            event_session_id="event-session-2",
            timestamp=next_event_timestamp,
        )
    )
    await hass.async_block_till_done()

    image = await async_get_image(hass)
    assert image.content == b"updated image bytes"


async def test_camera_web_rtc(hass, auth, hass_ws_client):
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
    device_traits = {
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
    await async_setup_camera(hass, device_traits, auth=auth)

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_STREAMING
    assert cam.attributes["frontend_stream_type"] == STREAM_TYPE_WEB_RTC

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.my_camera",
            "offer": "a=recvonly",
        }
    )

    msg = await client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"]["answer"] == "v=0\r\ns=-\r\n"

    # Nest WebRTC cameras return a placeholder
    content = await async_get_image(hass)
    assert content.content_type == "image/jpeg"
    content = await async_get_image(hass, width=1024, height=768)
    assert content.content_type == "image/jpeg"


async def test_camera_web_rtc_unsupported(hass, auth, hass_ws_client):
    """Test a basic camera that supports web rtc."""
    await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_STREAMING
    assert cam.attributes["frontend_stream_type"] == STREAM_TYPE_HLS

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.my_camera",
            "offer": "a=recvonly",
        }
    )

    msg = await client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == "web_rtc_offer_failed"
    assert msg["error"]["message"].startswith("Camera does not support WebRTC")


async def test_camera_web_rtc_offer_failure(hass, auth, hass_ws_client):
    """Test a basic camera that supports web rtc."""
    auth.responses = [
        aiohttp.web.Response(status=HTTPStatus.BAD_REQUEST),
    ]
    device_traits = {
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
    await async_setup_camera(hass, device_traits, auth=auth)

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_STREAMING

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.my_camera",
            "offer": "a=recvonly",
        }
    )

    msg = await client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == "web_rtc_offer_failed"
    assert msg["error"]["message"].startswith("Nest API error")


async def test_camera_multiple_streams(hass, auth, hass_ws_client):
    """Test a camera supporting multiple stream types."""
    expiration = utcnow() + datetime.timedelta(seconds=100)
    auth.responses = [
        # RTSP response
        make_stream_url_response(),
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
    device_traits = {
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
    await async_setup_camera(hass, device_traits, auth=auth)

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_STREAMING
    # Prefer WebRTC over RTSP/HLS
    assert cam.attributes["frontend_stream_type"] == STREAM_TYPE_WEB_RTC

    # RTSP stream
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.0.streamingToken"

    image = await async_get_image(hass)
    assert image.content == IMAGE_BYTES_FROM_STREAM

    # WebRTC stream
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.my_camera",
            "offer": "a=recvonly",
        }
    )

    msg = await client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"]["answer"] == "v=0\r\ns=-\r\n"
