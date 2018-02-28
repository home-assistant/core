"""
This component provides support for Xiaomi Cameras (HiSilicon Hi3518e V200).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.yi/
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

DEFAULT_BRAND = 'YI Home Camera'
DEFAULT_PASSWORD = ''
DEFAULT_PATH = '/tmp/sd/record'
DEFAULT_PORT = 21
DEFAULT_USERNAME = 'root'

CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
    vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string
})


async def async_setup_platform(hass,
                               config,
                               async_add_devices,
                               discovery_info=None):
    """Set up a Yi Camera."""
    _LOGGER.debug('Received configuration: %s', config)
    async_add_devices([YiCamera(hass, config)], True)


class YiCamera(Camera):
    """Define an implementation of a Yi Camera."""

    def __init__(self, hass, config):
        """Initialize."""
        super().__init__()
        self._extra_arguments = config.get(CONF_FFMPEG_ARGUMENTS)
        self._last_image = None
        self._last_url = None
        self._manager = hass.data[DATA_FFMPEG]
        self._name = config.get(CONF_NAME)
        self.host = config.get(CONF_HOST)
        self.port = config.get(CONF_PORT)
        self.path = config.get(CONF_PATH)
        self.user = config.get(CONF_USERNAME)
        self.passwd = config.get(CONF_PASSWORD)

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def brand(self):
        """Camera brand."""
        return DEFAULT_BRAND

    def get_latest_video_url(self):
        """Retrieve the latest video file from the customized Yi FTP server."""
        from ftplib import FTP, error_perm

        ftp = FTP(self.host)
        try:
            ftp.login(self.user, self.passwd)
        except error_perm as exc:
            _LOGGER.error('There was an error while logging into the camera')
            _LOGGER.debug(exc)
            return False

        try:
            ftp.cwd(self.path)
        except error_perm as exc:
            _LOGGER.error('Unable to find path: %s', self.path)
            _LOGGER.debug(exc)
            return False

        dirs = [d for d in ftp.nlst() if '.' not in d]
        if not dirs:
            _LOGGER.warning("There don't appear to be any uploaded videos")
            return False

        latest_dir = dirs[-1]
        ftp.cwd(latest_dir)
        videos = ftp.nlst()
        if not videos:
            _LOGGER.info('Video folder "%s" is empty; delaying', latest_dir)
            return False

        return 'ftp://{0}:{1}@{2}:{3}{4}/{5}/{6}'.format(
            self.user, self.passwd, self.host, self.port, self.path,
            latest_dir, videos[-1])

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
