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

_CAMERA_LAST_VISITOR = "{} Last Ring"
_CAMERA_LAST_MOTION = "{} Last Motion"
_CAMERA_LIVE = "{} Live"
_LAST_VISITOR_INTERVAL = datetime.timedelta(minutes=1)
_LAST_MOTION_INTERVAL = datetime.timedelta(minutes=1)
_LIVE_INTERVAL = datetime.timedelta(seconds=1)
_LOGGER = logging.getLogger(__name__)
_TIMEOUT = 10  # seconds


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the DoorBird camera platform."""
    for doorstation in hass.data[DOORBIRD_DOMAIN]:
        device = doorstation.device
        async_add_entities([
            DoorBirdCamera(
                device.live_image_url,
                _CAMERA_LIVE.format(doorstation.name),
                _LIVE_INTERVAL),
            DoorBirdCamera(
                device.history_image_url(1, 'doorbell'),
                _CAMERA_LAST_VISITOR.format(doorstation.name),
                _LAST_VISITOR_INTERVAL),
            DoorBirdCamera(
                device.history_image_url(1, 'motionsensor'),
                _CAMERA_LAST_MOTION.format(doorstation.name),
                _LAST_MOTION_INTERVAL),
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

    async def async_camera_image(self):
        """Pull a still image from the camera."""
        now = datetime.datetime.now()

        if self._last_image and now - self._last_update < self._interval:
            return self._last_image

        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(_TIMEOUT, loop=self.hass.loop):
                response = await websession.get(self._url)

            self._last_image = await response.read()
            self._last_update = now
            return self._last_image
        except asyncio.TimeoutError:
            _LOGGER.error("Camera image timed out")
            return self._last_image
        except aiohttp.ClientError as error:
            _LOGGER.error("Error getting camera image: %s", error)
            return self._last_image
