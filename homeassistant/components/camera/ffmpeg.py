"""
Support for Cameras with FFmpeg as decoder.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.ffmpeg/
"""
import logging
from contextlib import closing

import voluptuous as vol

from homeassistant.components.camera import Camera
from homeassistant.components.camera.mjpeg import extract_image_from_mjpeg
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_PLATFORM

REQUIREMENTS = ["ha-ffmpeg==0.4"]

CONF_INPUT = 'input'
CONF_FFMPEG_BIN = 'ffmpeg_bin'
CONF_EXTRA_ARGUMENTS = 'extra_arguments'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): "ffmpeg",
    vol.Optional(CONF_NAME, default="FFmpeg"): cv.string,
    vol.Required(CONF_INPUT): cv.string,
    vol.Optional(CONF_FFMPEG_BIN, default="ffmpeg"): cv.string,
    vol.Optional(CONF_EXTRA_ARGUMENTS): cv.string,
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup a FFmpeg Camera."""
    add_devices_callback([FFmpegCamera(config)])


class FFmpegCamera(Camera):
    """An implementation of an FFmpeg camera."""

    def __init__(self, config):
        """Initialize a FFmpeg camera."""
        super().__init__()
        self._name = config.get(CONF_NAME)
        self._input = config.get(CONF_INPUT)
        self._extra_arguments = config.get(CONF_EXTRA_ARGUMENTS)
        self._ffmpeg_bin = config.get(CONF_FFMPEG_BIN)

    def _ffmpeg_stream(self):
        """Return a FFmpeg process object."""
        from haffmpeg import CameraMjpeg

        ffmpeg = CameraMjpeg(self._ffmpeg_bin)
        ffmpeg.open_camera(self._input, extra_cmd=self._extra_arguments)
        return ffmpeg

    def camera_image(self):
        """Return a still image response from the camera."""
        with closing(self._ffmpeg_stream()) as stream:
            return extract_image_from_mjpeg(stream)

    def mjpeg_stream(self, response):
        """Generate an HTTP MJPEG stream from the camera."""
        stream = self._ffmpeg_stream()
        return response(
            stream,
            mimetype='multipart/x-mixed-replace;boundary=ffserver',
            direct_passthrough=True
        )

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
