"""
Support for Canary camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.canary/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.components.canary import DATA_CANARY, DEFAULT_TIMEOUT
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.util import Throttle

CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'

DEPENDENCIES = ['canary', 'ffmpeg']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SESSION_RENEW = timedelta(seconds=90)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Canary sensors."""
    data = hass.data[DATA_CANARY]
    devices = []

    for location in data.locations:
        for device in location.devices:
            if device.is_online:
                devices.append(
                    CanaryCamera(hass, data, location, device, DEFAULT_TIMEOUT,
                                 config.get(CONF_FFMPEG_ARGUMENTS)))

    add_entities(devices, True)


class CanaryCamera(Camera):
    """An implementation of a Canary security camera."""

    def __init__(self, hass, data, location, device, timeout, ffmpeg_args):
        """Initialize a Canary security camera."""
        super().__init__()

        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = ffmpeg_args
        self._data = data
        self._location = location
        self._device = device
        self._timeout = timeout
        self._live_stream_session = None

    @property
    def name(self):
        """Return the name of this device."""
        return self._device.name

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._location.is_recording

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return not self._location.is_recording

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        self.renew_live_stream_session()

        from haffmpeg import ImageFrame, IMAGE_JPEG
        ffmpeg = ImageFrame(self._ffmpeg.binary, loop=self.hass.loop)
        image = await asyncio.shield(ffmpeg.get_image(
            self._live_stream_session.live_stream_url,
            output_format=IMAGE_JPEG,
            extra_cmd=self._ffmpeg_arguments), loop=self.hass.loop)
        return image

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        if self._live_stream_session is None:
            return

        from haffmpeg import CameraMjpeg
        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        await stream.open_camera(
            self._live_stream_session.live_stream_url,
            extra_cmd=self._ffmpeg_arguments)

        try:
            return await async_aiohttp_proxy_stream(
                self.hass, request, stream,
                'multipart/x-mixed-replace;boundary=ffserver')
        finally:
            await stream.close()

    @Throttle(MIN_TIME_BETWEEN_SESSION_RENEW)
    def renew_live_stream_session(self):
        """Renew live stream session."""
        self._live_stream_session = self._data.get_live_stream_session(
            self._device)
