"""
This component provides support for Xiaomi Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.xiaomi/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import (CONF_HOST, CONF_NAME, CONF_PATH,
                                 CONF_PASSWORD, CONF_PORT, CONF_USERNAME)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream

DEPENDENCIES = ['ffmpeg']
_LOGGER = logging.getLogger(__name__)

DEFAULT_BRAND = 'Xiaomi Home Camera'
DEFAULT_PATH = '/media/mmcblk0p1/record'
DEFAULT_PORT = 21
DEFAULT_USERNAME = 'root'

CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'
CONF_MODEL = 'model'

MODEL_YI = 'yi'
MODEL_XIAOFANG = 'xiaofang'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_MODEL): vol.Any(MODEL_YI,
                                      MODEL_XIAOFANG),
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
    vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string
})


async def async_setup_platform(hass,
                               config,
                               async_add_entities,
                               discovery_info=None):
    """Set up a Xiaomi Camera."""
    _LOGGER.debug('Received configuration for model %s', config[CONF_MODEL])
    async_add_entities([XiaomiCamera(hass, config)])


class XiaomiCamera(Camera):
    """Define an implementation of a Xiaomi Camera."""

    def __init__(self, hass, config):
        """Initialize."""
        super().__init__()
        self._extra_arguments = config.get(CONF_FFMPEG_ARGUMENTS)
        self._last_image = None
        self._last_url = None
        self._manager = hass.data[DATA_FFMPEG]
        self._name = config[CONF_NAME]
        self.host = config[CONF_HOST]
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

    def get_latest_video_url(self):
        """Retrieve the latest video file from the Xiaomi Camera FTP server."""
        from ftplib import FTP, error_perm

        ftp = FTP(self.host)
        try:
            ftp.login(self.user, self.passwd)
        except error_perm as exc:
            _LOGGER.error('Camera login failed: %s', exc)
            return False

        try:
            ftp.cwd(self.path)
        except error_perm as exc:
            _LOGGER.error('Unable to find path: %s - %s', self.path, exc)
            return False

        dirs = [d for d in ftp.nlst() if '.' not in d]
        if not dirs:
            _LOGGER.warning("There don't appear to be any folders")
            return False

        first_dir = dirs[-1]
        try:
            ftp.cwd(first_dir)
        except error_perm as exc:
            _LOGGER.error('Unable to find path: %s - %s', first_dir, exc)
            return False

        if self._model == MODEL_XIAOFANG:
            dirs = [d for d in ftp.nlst() if '.' not in d]
            if not dirs:
                _LOGGER.warning("There don't appear to be any uploaded videos")
                return False

            latest_dir = dirs[-1]
            ftp.cwd(latest_dir)

        videos = [v for v in ftp.nlst() if '.tmp' not in v]
        if not videos:
            _LOGGER.info('Video folder "%s" is empty; delaying', latest_dir)
            return False

        if self._model == MODEL_XIAOFANG:
            video = videos[-2]
        else:
            video = videos[-1]

        return 'ftp://{0}:{1}@{2}:{3}{4}/{5}'.format(
            self.user, self.passwd, self.host, self.port, ftp.pwd(), video)

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        from haffmpeg import ImageFrame, IMAGE_JPEG

        url = await self.hass.async_add_job(self.get_latest_video_url)
        if url != self._last_url:
            ffmpeg = ImageFrame(self._manager.binary, loop=self.hass.loop)
            self._last_image = await asyncio.shield(ffmpeg.get_image(
                url, output_format=IMAGE_JPEG,
                extra_cmd=self._extra_arguments), loop=self.hass.loop)
            self._last_url = url

        return self._last_image

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        from haffmpeg import CameraMjpeg

        stream = CameraMjpeg(self._manager.binary, loop=self.hass.loop)
        await stream.open_camera(
            self._last_url, extra_cmd=self._extra_arguments)

        await async_aiohttp_proxy_stream(
            self.hass, request, stream,
            'multipart/x-mixed-replace;boundary=ffserver')
        await stream.close()
