"""
Support for Cameras with FFmpeg as decoder.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.ffmpeg/
"""
import asyncio
import logging

import voluptuous as vol
from aiohttp import web

from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.components.ffmpeg import (
    DATA_FFMPEG, CONF_INPUT, CONF_EXTRA_ARGUMENTS)
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME

DEPENDENCIES = ['ffmpeg']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'FFmpeg'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_INPUT): cv.string,
    vol.Optional(CONF_EXTRA_ARGUMENTS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup a FFmpeg Camera."""
    if not hass.data[DATA_FFMPEG].async_run_test(config.get(CONF_INPUT)):
        return
    async_add_devices([FFmpegCamera(hass, config)])


class FFmpegCamera(Camera):
    """An implementation of an FFmpeg camera."""

    def __init__(self, hass, config):
        """Initialize a FFmpeg camera."""
        super().__init__()

        self._manager = hass.data[DATA_FFMPEG]
        self._name = config.get(CONF_NAME)
        self._input = config.get(CONF_INPUT)
        self._extra_arguments = config.get(CONF_EXTRA_ARGUMENTS)

    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        from haffmpeg import ImageFrame, IMAGE_JPEG
        ffmpeg = ImageFrame(self._manager.binary, loop=self.hass.loop)

        image = yield from ffmpeg.get_image(
            self._input, output_format=IMAGE_JPEG,
            extra_cmd=self._extra_arguments)
        return image

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        from haffmpeg import CameraMjpeg

        stream = CameraMjpeg(self._manager.binary, loop=self.hass.loop)
        yield from stream.open_camera(
            self._input, extra_cmd=self._extra_arguments)

        response = web.StreamResponse()
        response.content_type = 'multipart/x-mixed-replace;boundary=ffserver'

        yield from response.prepare(request)

        try:
            while True:
                data = yield from stream.read(102400)
                if not data:
                    break
                response.write(data)

        except asyncio.CancelledError:
            _LOGGER.debug("Close stream by frontend.")
            response = None

        finally:
            yield from stream.close()
            if response is not None:
                yield from response.write_eof()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
