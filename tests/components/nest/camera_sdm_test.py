"""
Test for Nest cameras platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

import datetime
from unittest.mock import patch

import aiohttp
from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage
import pytest

from homeassistant.components import camera
from homeassistant.components.camera import STATE_IDLE
from homeassistant.exceptions import HomeAssistantError
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
    event_id: str = MOTION_EVENT_ID, timestamp: datetime.datetime = None
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
                        "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
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


async def async_get_image(hass):
    """Get image from the camera, a wrapper around camera.async_get_image."""
    # Note: this patches ImageFrame to simulate decoding an image from a live
    # stream, however the test may not use it. Tests assert on the image
    # contents to determine if the image came from the live stream or event.
    with patch(
        "homeassistant.components.ffmpeg.ImageFrame.get_image",
        autopatch=True,
        return_value=IMAGE_BYTES_FROM_STREAM,
    ):
        return await camera.async_get_image(hass, "camera.my_camera")


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
    assert camera.state == STATE_IDLE

    registry = await hass.helpers.entity_registry.async_get_registry()
    entry = registry.async_get("camera.my_camera")
    assert entry.unique_id == "some-device-id-camera"
    assert entry.original_name == "My Camera"
    assert entry.domain == "camera"

    device_registry = await hass.helpers.device_registry.async_get_registry()
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
    assert cam.state == STATE_IDLE

    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.0.streamingToken"

    image = await async_get_image(hass)
    assert image.content == IMAGE_BYTES_FROM_STREAM


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

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_IDLE

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
    assert cam.state == STATE_IDLE

    # The stream is expired, but we return it anyway
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.1.streamingToken"

    await fire_alarm(hass, now)

    # Second attempt sees that the stream is expired and refreshes
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"


async def test_camera_removed(hass, auth):
    """Test case where entities are removed and stream tokens expired."""
    subscriber = await async_setup_camera(
        hass,
        DEVICE_TRAITS,
        auth=auth,
    )

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_IDLE

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
    assert len(hass.states.async_all()) == 0


async def test_refresh_expired_stream_failure(hass, auth):
    """Tests a failure when refreshing the stream."""
    now = utcnow()
    stream_1_expiration = now + datetime.timedelta(seconds=90)
    stream_2_expiration = now + datetime.timedelta(seconds=180)
    auth.responses = [
        make_stream_url_response(expiration=stream_1_expiration, token_num=1),
        # Extending the stream fails with arbitrary error
        aiohttp.web.Response(status=500),
        # Next attempt to get a stream fetches a new url
        make_stream_url_response(expiration=stream_2_expiration, token_num=2),
    ]
    await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_IDLE

    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.1.streamingToken"

    # Fire alarm when stream is nearing expiration, causing it to be extended.
    # The stream expires.
    next_update = now + datetime.timedelta(seconds=65)
    await fire_alarm(hass, next_update)

    # The stream is entirely refreshed
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"


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
        aiohttp.web.Response(status=500),
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
        aiohttp.web.Response(status=500),
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


async def test_event_image_becomes_expired(hass, auth):
    """Test fallback for an event event image that has been cleaned up on expiration."""
    subscriber = await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("camera.my_camera")

    event_timestamp = utcnow()
    await subscriber.async_receive_event(make_motion_event(timestamp=event_timestamp))
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

    # Event image is still valid before expiration
    next_update = event_timestamp + datetime.timedelta(seconds=25)
    await fire_alarm(hass, next_update)

    image = await async_get_image(hass)
    assert image.content == IMAGE_BYTES_FROM_EVENT

    # Fire an alarm well after expiration, removing image from cache
    # Note: This test does not override the "now" logic within the underlying
    # python library that tracks active events. Instead, it exercises the
    # alarm behavior only. That is, the library may still think the event is
    # active even though Home Assistant does not due to patching time.
    next_update = event_timestamp + datetime.timedelta(seconds=180)
    await fire_alarm(hass, next_update)

    image = await async_get_image(hass)
    assert image.content == b"updated image bytes"


async def test_multiple_event_images(hass, auth):
    """Test fallback for an event event image that has been cleaned up on expiration."""
    subscriber = await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("camera.my_camera")

    event_timestamp = utcnow()
    await subscriber.async_receive_event(make_motion_event(timestamp=event_timestamp))
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
        make_motion_event(event_id="updated-event-id", timestamp=next_event_timestamp)
    )
    await hass.async_block_till_done()

    image = await async_get_image(hass)
    assert image.content == b"updated image bytes"
