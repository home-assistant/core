"""Support for viewing the camera feed from a DoorBird video doorbell."""
import asyncio
import datetime
import logging

import aiohttp
import async_timeout

from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.util.dt as dt_util

from . import DOMAIN as DOORBIRD_DOMAIN

_LAST_VISITOR_INTERVAL = datetime.timedelta(minutes=1)
_LAST_MOTION_INTERVAL = datetime.timedelta(minutes=1)
_LIVE_INTERVAL = datetime.timedelta(seconds=1)
_LOGGER = logging.getLogger(__name__)
_TIMEOUT = 10  # seconds


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the DoorBird camera platform."""
    for doorstation in hass.data[DOORBIRD_DOMAIN]:
        device = doorstation.device
        async_add_entities(
            [
                DoorBirdCamera(
                    device.live_image_url,
                    f"{doorstation.name} Live",
                    _LIVE_INTERVAL,
                    device.rtsp_live_video_url,
                ),
                DoorBirdCamera(
                    device.history_image_url(1, "doorbell"),
                    f"{doorstation.name} Last Ring",
                    _LAST_VISITOR_INTERVAL,
                ),
                DoorBirdCamera(
                    device.history_image_url(1, "motionsensor"),
                    f"{doorstation.name} Last Motion",
                    _LAST_MOTION_INTERVAL,
                ),
            ]
        )


class DoorBirdCamera(Camera):
    """The camera on a DoorBird device."""

    def __init__(self, url, name, interval=None, stream_url=None):
        """Initialize the camera on a DoorBird device."""
        self._url = url
        self._stream_url = stream_url
        self._name = name
        self._last_image = None
        self._supported_features = SUPPORT_STREAM if self._stream_url else 0
        self._interval = interval or datetime.timedelta
        self._last_update = datetime.datetime.min
        super().__init__()

    async def stream_source(self):
        """Return the stream source."""
        return self._stream_url

    @property
    def supported_features(self):
        """Return supported features."""
        return self._supported_features

    @property
    def name(self):
        """Get the name of the camera."""
        return self._name

    async def async_camera_image(self):
        """Pull a still image from the camera."""
        now = dt_util.utcnow()

        if self._last_image and now - self._last_update < self._interval:
            return self._last_image

        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(_TIMEOUT):
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
