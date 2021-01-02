"""
Test for Nest cameras platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

import datetime
from unittest.mock import patch

import aiohttp
from google_nest_sdm.device import Device
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
}
DATETIME_FORMAT = "YY-MM-DDTHH:MM:SS"
DOMAIN = "nest"


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
    now = utcnow()
    expiration = now + datetime.timedelta(seconds=100)
    auth.responses = [
        aiohttp.web.json_response(
            {
                "results": {
                    "streamUrls": {
                        "rtspUrl": "rtsp://some/url?auth=g.0.streamingToken"
                    },
                    "streamExtensionToken": "g.1.extensionToken",
                    "streamToken": "g.0.streamingToken",
                    "expiresAt": expiration.isoformat(timespec="seconds"),
                },
            }
        )
    ]
    await async_setup_camera(hass, DEVICE_TRAITS, auth=auth)

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_IDLE

    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.0.streamingToken"

    with patch(
        "homeassistant.components.ffmpeg.ImageFrame.get_image",
        autopatch=True,
        return_value=b"image bytes",
    ):
        image = await camera.async_get_image(hass, "camera.my_camera")

    assert image.content == b"image bytes"


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

    # Currently on support getting the image from a live stream
    with pytest.raises(HomeAssistantError):
        image = await camera.async_get_image(hass, "camera.my_camera")
        assert image is None


async def test_refresh_expired_stream_token(hass, auth):
    """Test a camera stream expiration and refresh."""
    now = utcnow()
    stream_1_expiration = now + datetime.timedelta(seconds=90)
    stream_2_expiration = now + datetime.timedelta(seconds=180)
    stream_3_expiration = now + datetime.timedelta(seconds=360)
    auth.responses = [
        # Stream URL #1
        aiohttp.web.json_response(
            {
                "results": {
                    "streamUrls": {
                        "rtspUrl": "rtsp://some/url?auth=g.1.streamingToken"
                    },
                    "streamExtensionToken": "g.1.extensionToken",
                    "streamToken": "g.1.streamingToken",
                    "expiresAt": stream_1_expiration.isoformat(timespec="seconds"),
                },
            }
        ),
        # Stream URL #2
        aiohttp.web.json_response(
            {
                "results": {
                    "streamExtensionToken": "g.2.extensionToken",
                    "streamToken": "g.2.streamingToken",
                    "expiresAt": stream_2_expiration.isoformat(timespec="seconds"),
                },
            }
        ),
        # Stream URL #3
        aiohttp.web.json_response(
            {
                "results": {
                    "streamExtensionToken": "g.3.extensionToken",
                    "streamToken": "g.3.streamingToken",
                    "expiresAt": stream_3_expiration.isoformat(timespec="seconds"),
                },
            }
        ),
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
        aiohttp.web.json_response(
            {
                "results": {
                    "streamUrls": {
                        "rtspUrl": "rtsp://some/url?auth=g.1.streamingToken"
                    },
                    "streamExtensionToken": "g.1.extensionToken",
                    "streamToken": "g.1.streamingToken",
                    "expiresAt": stream_1_expiration.isoformat(timespec="seconds"),
                },
            }
        ),
        aiohttp.web.json_response(
            {
                "results": {
                    "streamUrls": {
                        "rtspUrl": "rtsp://some/url?auth=g.2.streamingToken"
                    },
                    "streamExtensionToken": "g.2.extensionToken",
                    "streamToken": "g.2.streamingToken",
                    "expiresAt": stream_2_expiration.isoformat(timespec="seconds"),
                },
            }
        ),
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

    # The stream is expired, but we return it anyway
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.1.streamingToken"

    await fire_alarm(hass, now)

    # Second attempt sees that the stream is expired and refreshes
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"


async def test_camera_removed(hass, auth):
    """Test case where entities are removed and stream tokens expired."""
    now = utcnow()
    expiration = now + datetime.timedelta(seconds=100)
    auth.responses = [
        aiohttp.web.json_response(
            {
                "results": {
                    "streamUrls": {
                        "rtspUrl": "rtsp://some/url?auth=g.0.streamingToken"
                    },
                    "streamExtensionToken": "g.1.extensionToken",
                    "streamToken": "g.0.streamingToken",
                    "expiresAt": expiration.isoformat(timespec="seconds"),
                },
            }
        ),
        aiohttp.web.json_response({"results": {}}),
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
    assert stream_source == "rtsp://some/url?auth=g.0.streamingToken"

    for config_entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_remove(config_entry.entry_id)
    assert len(hass.states.async_all()) == 0


async def test_refresh_expired_stream_failure(hass, auth):
    """Tests a failure when refreshing the stream."""
    now = utcnow()
    stream_1_expiration = now + datetime.timedelta(seconds=90)
    stream_2_expiration = now + datetime.timedelta(seconds=180)
    auth.responses = [
        aiohttp.web.json_response(
            {
                "results": {
                    "streamUrls": {
                        "rtspUrl": "rtsp://some/url?auth=g.1.streamingToken"
                    },
                    "streamExtensionToken": "g.1.extensionToken",
                    "streamToken": "g.1.streamingToken",
                    "expiresAt": stream_1_expiration.isoformat(timespec="seconds"),
                },
            }
        ),
        # Extending the stream fails with arbitrary error
        aiohttp.web.Response(status=500),
        # Next attempt to get a stream fetches a new url
        aiohttp.web.json_response(
            {
                "results": {
                    "streamUrls": {
                        "rtspUrl": "rtsp://some/url?auth=g.2.streamingToken"
                    },
                    "streamExtensionToken": "g.2.extensionToken",
                    "streamToken": "g.2.streamingToken",
                    "expiresAt": stream_2_expiration.isoformat(timespec="seconds"),
                },
            }
        ),
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

    # Fire alarm when stream is nearing expiration, causing it to be extended.
    # The stream expires.
    next_update = now + datetime.timedelta(seconds=65)
    await fire_alarm(hass, next_update)

    # The stream is entirely refreshed
    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.2.streamingToken"
