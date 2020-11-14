"""This component provides support for Reolink IP cameras."""
import asyncio
import logging

from haffmpeg.camera import CameraMjpeg
import voluptuous as vol

from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream

from .entity import ReolinkEntity

_LOGGER = logging.getLogger(__name__)

SERVICE_PTZ_CONTROL = "ptz_control"


@asyncio.coroutine
async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up a Reolink IP Camera."""

    camera = ReolinkCamera(hass, config_entry)

    if camera.ptz_support:
        platform = entity_platform.current_platform.get()

        platform.async_register_entity_service(
            SERVICE_PTZ_CONTROL,
            {
                vol.Required("command"): cv.string,
                vol.Optional("preset"): cv.positive_int,
                vol.Optional("speed"): cv.positive_int,
            },
            "ptz_control",
        )

    async_add_devices([camera])


class ReolinkCamera(ReolinkEntity, Camera):
    """An implementation of a Reolink IP camera."""

    def __init__(self, hass, config):
        """Initialize a Reolink camera."""
        ReolinkEntity.__init__(self, hass, config)
        Camera.__init__(self)

        self._hass = hass
        self._manager = self._hass.data[DATA_FFMPEG]
        self._last_image = None
        self._ptz_commands = {
            "AUTO": "Auto",
            "DOWN": "Down",
            "FOCUSDEC": "FocusDec",
            "FOCUSINC": "FocusInc",
            "LEFT": "Left",
            "LEFTDOWN": "LeftDown",
            "LEFTUP": "LeftUp",
            "RIGHT": "Right",
            "RIGHTDOWN": "RightDown",
            "RIGHTUP": "RightUp",
            "STOP": "Stop",
            "TOPOS": "ToPos",
            "UP": "Up",
            "ZOOMDEC": "ZoomDec",
            "ZOOMINC": "ZoomInc",
        }

    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"reolink_{self._base.api.mac_address}"

    @property
    def name(self):
        """Return the name of this camera."""
        return self._base.api.name

    @property
    def ptz_support(self):
        """Return whether the camera has PTZ support."""
        return self._base.api.ptz_support

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_STREAM

    async def stream_source(self):
        """Return the source of the stream."""
        return await self._base.api.get_stream_source()

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        stream_source = await self.stream_source()

        stream = CameraMjpeg(self._manager.binary, loop=self._hass.loop)
        await stream.open_camera(stream_source)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self._hass,
                request,
                stream_reader,
                self._manager.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        return await self._base.api.get_snapshot()

    async def ptz_control(self, command, **kwargs):
        """Pass PTZ command to the camera."""
        if not self.ptz_support:
            _LOGGER.error("PTZ is not supported on this device")
            return

        await self._base.api.set_ptz_command(
            command=self._ptz_commands[command], **kwargs
        )
