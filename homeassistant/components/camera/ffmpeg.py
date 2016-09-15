"""
Support for Cameras with FFmpeg as decoder.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.ffmpeg/
"""
import logging

import voluptuous as vol

from homeassistant.components.camera import (Camera, PLATFORM_SCHEMA)
from homeassistant.components.ffmpeg import (
    run_test, get_binary, CONF_INPUT, CONF_EXTRA_ARGUMENTS)
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


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a FFmpeg Camera."""
    if not run_test(config.get(CONF_INPUT)):
        return
    add_devices([FFmpegCamera(config)])


class FFmpegCamera(Camera):
    """An implementation of an FFmpeg camera."""

    def __init__(self, config):
        """Initialize a FFmpeg camera."""
        super().__init__()
        self._name = config.get(CONF_NAME)
        self._input = config.get(CONF_INPUT)
        self._extra_arguments = config.get(CONF_EXTRA_ARGUMENTS)

    def camera_image(self):
        """Return a still image response from the camera."""
        from haffmpeg import ImageSingle, IMAGE_JPEG
        ffmpeg = ImageSingle(get_binary())

        return ffmpeg.get_image(self._input, output_format=IMAGE_JPEG,
                                extra_cmd=self._extra_arguments)

    def mjpeg_stream(self, response):
        """Generate an HTTP MJPEG stream from the camera."""
        from haffmpeg import CameraMjpeg

        stream = CameraMjpeg(get_binary())
        stream.open_camera(self._input, extra_cmd=self._extra_arguments)
        return response(
            stream,
            mimetype='multipart/x-mixed-replace;boundary=ffserver',
            direct_passthrough=True
        )

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
