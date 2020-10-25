"""
Test for Nest cameras platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.device import Device

from homeassistant.components import camera
from homeassistant.components.camera import STATE_IDLE

from .common import async_setup_sdm_platform

PLATFORM = "camera"
CAMERA_DEVICE_TYPE = "sdm.devices.types.CAMERA"
DEVICE_ID = "some-device-id"


class FakeResponse:
    """A fake web response used for returning results of commands."""

    def __init__(self, json):
        """Initialize the FakeResponse."""
        self._json = json

    def raise_for_status(self):
        """Mimics a successful response status."""
        pass

    async def json(self):
        """Return a dict with the response."""
        return self._json


class FakeAuth(AbstractAuth):
    """Fake authentication object that returns fake responses."""

    def __init__(self, response: FakeResponse):
        """Initialize the FakeAuth."""
        super().__init__(None, "")
        self._response = response

    async def async_get_access_token(self):
        """Return a fake access token."""
        return "some-token"

    async def creds(self):
        """Return a fake creds."""
        return None

    async def request(self, method: str, url: str, **kwargs):
        """Pass through the FakeResponse."""
        return self._response


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
    await async_setup_camera(
        hass,
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
            },
        },
    )

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


async def test_camera_stream(hass):
    """Test a basic camera and fetch its live stream."""
    response = FakeResponse(
        {
            "results": {
                "streamUrls": {"rtspUrl": "rtsp://some/url?auth=g.0.streamingToken"},
                "streamExtensionToken": "g.1.extensionToken",
                "streamToken": "g.0.streamingToken",
                "expiresAt": "2018-01-04T18:30:00.000Z",
            },
        }
    )
    await async_setup_camera(
        hass,
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
            },
        },
        auth=FakeAuth(response),
    )

    assert len(hass.states.async_all()) == 1
    cam = hass.states.get("camera.my_camera")
    assert cam is not None
    assert cam.state == STATE_IDLE

    stream_source = await camera.async_get_stream_source(hass, "camera.my_camera")
    assert stream_source == "rtsp://some/url?auth=g.0.streamingToken"
