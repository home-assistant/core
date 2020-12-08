"""Support for Cameras with FFmpeg as decoder."""

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, SUPPORT_STREAM, Camera
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
import homeassistant.helpers.config_validation as cv

from . import CONF_EXTRA_ARGUMENTS, CONF_INPUT, DATA_FFMPEG, async_get_image

DEFAULT_NAME = "FFmpeg"
DEFAULT_ARGUMENTS = "-pred 1"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_INPUT): cv.string,
        vol.Optional(CONF_EXTRA_ARGUMENTS, default=DEFAULT_ARGUMENTS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a FFmpeg camera."""
    async_add_entities([FFmpegCamera(hass, config)])


class FFmpegCamera(Camera):
    """An implementation of an FFmpeg camera."""

    def __init__(self, hass, config):
        """Initialize a FFmpeg camera."""
        super().__init__()

        self._manager = hass.data[DATA_FFMPEG]
        self._name = config.get(CONF_NAME)
        self._input = config.get(CONF_INPUT)
        self._extra_arguments = config.get(CONF_EXTRA_ARGUMENTS)

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_STREAM

    async def stream_source(self):
        """Return the stream source."""
        return self._input.split(" ")[-1]

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        return await async_get_image(
            self.hass,
            self._input,
            output_format=IMAGE_JPEG,
            extra_cmd=self._extra_arguments,
        )

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""

        stream = CameraMjpeg(self._manager.binary, loop=self.hass.loop)
        await stream.open_camera(self._input, extra_cmd=self._extra_arguments)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._manager.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
