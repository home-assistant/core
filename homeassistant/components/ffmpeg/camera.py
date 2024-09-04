"""Support for Cameras with FFmpeg as decoder."""

from __future__ import annotations

from typing import Any

from aiohttp import web
from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG
import voluptuous as vol

from homeassistant.components.camera import (
    PLATFORM_SCHEMA as CAMERA_PLATFORM_SCHEMA,
    Camera,
    CameraEntityFeature,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_EXTRA_ARGUMENTS,
    CONF_INPUT,
    DATA_FFMPEG,
    FFmpegManager,
    async_get_image,
)

DEFAULT_NAME = "FFmpeg"
DEFAULT_ARGUMENTS = "-pred 1"

PLATFORM_SCHEMA = CAMERA_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_INPUT): cv.string,
        vol.Optional(CONF_EXTRA_ARGUMENTS, default=DEFAULT_ARGUMENTS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a FFmpeg camera."""
    async_add_entities([FFmpegCamera(hass, config)])


class FFmpegCamera(Camera):
    """An implementation of an FFmpeg camera."""

    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize a FFmpeg camera."""
        super().__init__()

        self._manager: FFmpegManager = hass.data[DATA_FFMPEG]
        self._name: str = config[CONF_NAME]
        self._input: str = config[CONF_INPUT]
        self._extra_arguments: str = config[CONF_EXTRA_ARGUMENTS]

    async def stream_source(self) -> str:
        """Return the stream source."""
        return self._input.split(" ")[-1]

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        return await async_get_image(
            self.hass,
            self._input,
            output_format=IMAGE_JPEG,
            extra_cmd=self._extra_arguments,
        )

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse:
        """Generate an HTTP MJPEG stream from the camera."""

        stream = CameraMjpeg(self._manager.binary)
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
    def name(self) -> str:
        """Return the name of this camera."""
        return self._name
