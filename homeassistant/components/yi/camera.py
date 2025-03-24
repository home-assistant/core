"""Support for Xiaomi Cameras (HiSilicon Hi3518e V200)."""

from __future__ import annotations

import logging

from aioftp import Client, StatusCodeError
from haffmpeg.camera import CameraMjpeg
import voluptuous as vol

from homeassistant.components import ffmpeg
from homeassistant.components.camera import (
    PLATFORM_SCHEMA as CAMERA_PLATFORM_SCHEMA,
    Camera,
)
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_BRAND = "YI Home Camera"
DEFAULT_PASSWORD = ""
DEFAULT_PATH = "/tmp/sd/record"  # noqa: S108
DEFAULT_PORT = 21
DEFAULT_USERNAME = "root"
DEFAULT_ARGUMENTS = "-pred 1"

CONF_FFMPEG_ARGUMENTS = "ffmpeg_arguments"

PLATFORM_SCHEMA = CAMERA_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_FFMPEG_ARGUMENTS, default=DEFAULT_ARGUMENTS): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a Yi Camera."""
    async_add_entities([YiCamera(hass, config)], True)


class YiCamera(Camera):
    """Define an implementation of a Yi Camera."""

    def __init__(self, hass, config):
        """Initialize."""
        super().__init__()
        self._extra_arguments = config.get(CONF_FFMPEG_ARGUMENTS)
        self._last_image = None
        self._last_url = None
        self._manager = get_ffmpeg_manager(hass)
        self._name = config[CONF_NAME]
        self._is_on = True
        self.host = config[CONF_HOST]
        self.port = config[CONF_PORT]
        self.path = config[CONF_PATH]
        self.user = config[CONF_USERNAME]
        self.passwd = config[CONF_PASSWORD]

    @property
    def brand(self):
        """Camera brand."""
        return DEFAULT_BRAND

    @property
    def is_on(self):
        """Determine whether the camera is on."""
        return self._is_on

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    async def _get_latest_video_url(self):
        """Retrieve the latest video file from the customized Yi FTP server."""
        ftp = Client()
        try:
            await ftp.connect(self.host)
            await ftp.login(self.user, self.passwd)
        except (ConnectionRefusedError, StatusCodeError) as err:
            raise PlatformNotReady(err) from err

        try:
            await ftp.change_directory(self.path)
            dirs = []
            for path, attrs in await ftp.list():
                if attrs["type"] == "dir" and "." not in str(path):
                    dirs.append(path)
            latest_dir = dirs[-1]
            await ftp.change_directory(latest_dir)

            videos = []
            for path, _ in await ftp.list():
                videos.append(path)
            if not videos:
                _LOGGER.info('Video folder "%s" empty; delaying', latest_dir)
                return None

            await ftp.quit()
            self._is_on = True
            return (
                f"ftp://{self.user}:{self.passwd}@{self.host}:"
                f"{self.port}{self.path}/{latest_dir}/{videos[-1]}"
            )
        except (ConnectionRefusedError, StatusCodeError) as err:
            _LOGGER.error("Error while fetching video: %s", err)
            self._is_on = False
            return None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        url = await self._get_latest_video_url()
        if url and url != self._last_url:
            self._last_image = await ffmpeg.async_get_image(
                self.hass,
                url,
                extra_cmd=self._extra_arguments,
                width=width,
                height=height,
            )
            self._last_url = url

        return self._last_image

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        if not self._is_on:
            return None

        stream = CameraMjpeg(self._manager.binary)
        await stream.open_camera(self._last_url, extra_cmd=self._extra_arguments)

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
