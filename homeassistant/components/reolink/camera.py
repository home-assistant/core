"""This component provides support for Reolink IP cameras."""
import asyncio
import datetime
import logging

import voluptuous as vol
from haffmpeg.camera import CameraMjpeg
from homeassistant.components.camera import (
    ENTITY_IMAGE_URL,
    PLATFORM_SCHEMA,
    SUPPORT_STREAM,
    Camera,
)
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform, service
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import CONF_CHANNEL  # pylint:disable=unused-import
from .const import (
    BASE,
    CONF_PROTOCOL,
    CONF_STREAM,
    COORDINATOR,
    DOMAIN,
    STATE_IDLE,
    STATE_MOTION,
    STATE_NO_MOTION,
)
from .entity import ReolinkEntity

_LOGGER = logging.getLogger(__name__)

SERVICE_PTZ_CONTROL = "ptz_control"


@asyncio.coroutine
async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up a Reolink IP Camera."""

    camera = ReolinkCamera(hass, config_entry)

    if camera.hasPtz:
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
        self._hasPtz = False
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
        return f"reolink_{self._base._api.mac_address}"

    @property
    def name(self):
        """Return the name of this camera."""
        return self._base._api.name

    @property
    def hasPtz(self):
        """Return whether the camera has PTZ."""
        return self._base._api._hasPtz

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_STREAM

    async def stream_source(self):
        """Return the source of the stream."""
        return await self._base._api.get_stream_source()

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

    async def camera_image(self):
        """Return bytes of camera image."""
        return self._base._api.get_still_image()

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        return await self._base._api.get_snapshot()

    async def ptz_control(self, command, **kwargs):
        """Pass PTZ command to the camera."""
        await self._base._api.set_ptz_command(
            command=self._ptz_commands[command], **kwargs
        )
