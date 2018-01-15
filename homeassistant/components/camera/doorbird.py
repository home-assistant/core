"""
Support for viewing the camera feed from a DoorBird video doorbell.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.doorbird/
"""
import asyncio
import datetime
import logging

import aiohttp
import async_timeout

from homeassistant.components.camera import Camera
from homeassistant.components.doorbird import DOMAIN as DOORBIRD_DOMAIN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

DEPENDENCIES = ['doorbird']

_CAMERA_LAST_VISITOR = "DoorBird Last Ring"
_CAMERA_LIVE = "DoorBird Live"
_LAST_VISITOR_INTERVAL = datetime.timedelta(minutes=1)
_LIVE_INTERVAL = datetime.timedelta(seconds=1)
_LOGGER = logging.getLogger(__name__)
_TIMEOUT = 10  # seconds


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the DoorBird camera platform."""
    device = hass.data.get(DOORBIRD_DOMAIN)
    async_add_devices([
        DoorBirdCamera(device.live_image_url, _CAMERA_LIVE, _LIVE_INTERVAL),
        DoorBirdCamera(
            device.history_image_url(1, 'doorbell'), _CAMERA_LAST_VISITOR,
            _LAST_VISITOR_INTERVAL),
    ])


class DoorBirdCamera(Camera):
    """The camera on a DoorBird device."""

    def __init__(self, url, name, interval=None):
        """Initialize the camera on a DoorBird device."""
        self._url = url
        self._name = name
        self._last_image = None
        self._interval = interval or datetime.timedelta
        self._last_update = datetime.datetime.min
        super().__init__()

    @property
    def name(self):
        """Get the name of the camera."""
        return self._name

    @asyncio.coroutine
    def async_camera_image(self):
        """Pull a still image from the camera."""
        now = datetime.datetime.now()

        if self._last_image and now - self._last_update < self._interval:
            return self._last_image

        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(_TIMEOUT, loop=self.hass.loop):
                response = yield from websession.get(self._url)

            self._last_image = yield from response.read()
            self._last_update = now
            return self._last_image
        except asyncio.TimeoutError:
            _LOGGER.error("Camera image timed out")
            return self._last_image
        except aiohttp.ClientError as error:
            _LOGGER.error("Error getting camera image: %s", error)
            return self._last_image
