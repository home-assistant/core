"""Component providing support for Xiaomi Cameras."""

from __future__ import annotations

from ftplib import FTP, error_perm
import logging

from haffmpeg.camera import CameraMjpeg
import voluptuous as vol

from homeassistant.components import ffmpeg
from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_BRAND = "Xiaomi Home Camera"
DEFAULT_PATH = "/media/mmcblk0p1/record"
DEFAULT_PORT = 21
DEFAULT_USERNAME = "root"
DEFAULT_ARGUMENTS = "-pred 1"

CONF_FFMPEG_ARGUMENTS = "ffmpeg_arguments"

MODEL_YI = "yi"
MODEL_XIAOFANG = "xiaofang"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.template,
        vol.Required(CONF_MODEL): vol.Any(MODEL_YI, MODEL_XIAOFANG),
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
    """Set up a Xiaomi Camera."""
    _LOGGER.debug("Received configuration for model %s", config[CONF_MODEL])
    async_add_entities([XiaomiCamera(hass, config)])


class XiaomiCamera(Camera):
    """Define an implementation of a Xiaomi Camera."""

    def __init__(self, hass, config):
        """Initialize."""
        super().__init__()
        self._extra_arguments = config.get(CONF_FFMPEG_ARGUMENTS)
        self._last_image = None
        self._last_url = None
        self._manager = get_ffmpeg_manager(hass)
        self._name = config[CONF_NAME]
        self.host = config[CONF_HOST]
        self.host.hass = hass
        self._model = config[CONF_MODEL]
        self.port = config[CONF_PORT]
        self.path = config[CONF_PATH]
        self.user = config[CONF_USERNAME]
        self.passwd = config[CONF_PASSWORD]

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def brand(self):
        """Return the camera brand."""
        return DEFAULT_BRAND

    @property
    def model(self):
        """Return the camera model."""
        return self._model

    def get_latest_video_url(self, host):
        """Retrieve the latest video file from the Xiaomi Camera FTP server."""

        ftp = FTP(host)
        try:
            ftp.login(self.user, self.passwd)
        except error_perm as exc:
            _LOGGER.error("Camera login failed: %s", exc)
            return False

        try:
            ftp.cwd(self.path)
        except error_perm as exc:
            _LOGGER.error("Unable to find path: %s - %s", self.path, exc)
            return False

        dirs = [d for d in ftp.nlst() if "." not in d]
        if not dirs:
            _LOGGER.warning("There don't appear to be any folders")
            return False

        first_dir = latest_dir = dirs[-1]
        try:
            ftp.cwd(first_dir)
        except error_perm as exc:
            _LOGGER.error("Unable to find path: %s - %s", first_dir, exc)
            return False

        if self._model == MODEL_XIAOFANG:
            dirs = [d for d in ftp.nlst() if "." not in d]
            if not dirs:
                _LOGGER.warning("There don't appear to be any uploaded videos")
                return False

            latest_dir = dirs[-1]
            ftp.cwd(latest_dir)

        videos = [v for v in ftp.nlst() if ".tmp" not in v]
        if not videos:
            _LOGGER.info('Video folder "%s" is empty; delaying', latest_dir)
            return False

        if self._model == MODEL_XIAOFANG:
            video = videos[-2]
        else:
            video = videos[-1]

        return f"ftp://{self.user}:{self.passwd}@{host}:{self.port}{ftp.pwd()}/{video}"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""

        try:
            host = self.host.async_render(parse_result=False)
        except TemplateError as exc:
            _LOGGER.error("Error parsing template %s: %s", self.host, exc)
            return self._last_image

        url = await self.hass.async_add_executor_job(self.get_latest_video_url, host)
        if url != self._last_url:
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
