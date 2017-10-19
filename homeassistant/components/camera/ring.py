"""
This component provides support to the Ring Door Bell camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.ring/
"""
import asyncio
import logging

from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.components.ring import DATA_RING, CONF_ATTRIBUTION
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.util import dt as dt_util

CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'

DEPENDENCIES = ['ring', 'ffmpeg']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a Ring Door Bell IP Camera."""
    ring = hass.data[DATA_RING]

    cams = []
    for camera in ring.doorbells:
        cams.append(RingCam(hass, camera, config))

    async_add_devices(cams, True)
    return True


class RingCam(Camera):
    """An implementation of a Ring Door Bell camera."""

    def __init__(self, hass, camera, device_info):
        """Initialize a Ring Door Bell camera."""
        super(RingCam, self).__init__()
        self._camera = camera
        self._hass = hass
        self._name = self._camera.name
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = device_info.get(CONF_FFMPEG_ARGUMENTS)
        self._last_video_id = self._camera.last_recording_id
        self._video_url = self._camera.recording_url(self._last_video_id)
        self._expires_at = None
        self._utcnow = None

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        attrs['device_id'] = self._camera.id
        attrs['firmware'] = self._camera.firmware
        attrs['kind'] = self._camera.kind
        attrs['timezone'] = self._camera.timezone
        attrs['type'] = self._camera.family
        attrs['video_url'] = self._video_url
        attrs['video_id'] = self._last_video_id

        return attrs

    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        from haffmpeg import ImageFrame, IMAGE_JPEG
        ffmpeg = ImageFrame(self._ffmpeg.binary, loop=self.hass.loop)

        if self._video_url is None:
            return

        image = yield from asyncio.shield(ffmpeg.get_image(
            self._video_url, output_format=IMAGE_JPEG,
            extra_cmd=self._ffmpeg_arguments), loop=self.hass.loop)
        return image

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        from haffmpeg import CameraMjpeg

        if self._video_url is None:
            return

        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        yield from stream.open_camera(
            self._video_url, extra_cmd=self._ffmpeg_arguments)

        yield from async_aiohttp_proxy_stream(
            self.hass, request, stream,
            'multipart/x-mixed-replace;boundary=ffserver')
        yield from stream.close()

    def update(self):
        """Update camera entity and refresh attributes."""
        x_amz_expires = int(self._video_url.split('&')[0].split('=')[-1])
        x_amz_date = self._video_url.split('&')[1].split('=')[-1]

        self._expires_at = \
            timedelta(seconds=x_amz_expires) + \
            dt_util.as_utc(datetime.strptime(x_amz_date, "%Y%m%dT%H%M%SZ"))

        self._utcnow = dt_util.utcnow()

        # refresh last_video_id if a new video has been published
        if self._last_video_id != self._camera.last_recording_id:
            self._refresh_attrs()

        if self._utcnow >= self._expires_at:
            self._refresh_attrs()

    def _refresh_attrs(self):
        _LOGGER.debug("Updated Ring DoorBell camera attributes.")
        self._last_video_id = self._camera.last_recording_id
        self._video_url = self._camera.recording_url(self._last_video_id)
