"""
This component provides basic support for Xiaomi Cameras
(HiSilicon Hi3518e V200).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.yi/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream

DEPENDENCIES = ['ffmpeg']
REQUIREMENTS = ['aioftp==0.8.0']
_LOGGER = logging.getLogger(__name__)

DEFAULT_PASSWORD = ''
DEFAULT_PATH = '/tmp/sd/record'
DEFAULT_USERNAME = 'root'

CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST):
    cv.string,
    vol.Optional(CONF_PATH, default=DEFAULT_PATH):
    cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME):
    cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD):
    cv.string,
    vol.Optional(CONF_FFMPEG_ARGUMENTS):
    cv.string
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a Yi Camera."""
    import ftplib

    _LOGGER.debug('Received configuration: %s', config)

    # ftp_host = config.get(CONF_HOST)
    # ftp_path = config.get(CONF_PATH)
    # ftp_user = config.get(CONF_USERNAME)
    # ftp_pass = config.get(CONF_PASSWORD)

    # ftp = ftplib.FTP(ftp_host, user=ftp_user, passwd=ftp_pass)

    # # Attempt to login and return False if unsuccessful:
    # try:
    #     ftp.login()
    # except ftplib.error_perm:
    #     _LOGGER.error('Unable to login to camera')
    #     return False

    # # Attempt to CWD to the user-provided path and return False if unsucessful:
    # try:
    #     ftp.cwd(ftp_path)
    # except ftplib.error_perm:
    #     _LOGGER.error('Path does not exist on device: %s', ftp_path)
    #     return False

    async_add_devices([YiCamera(hass, config)], True)


def extract_image_from_mjpeg(stream):
    """Return an image from an MP4."""
    data = b''
    for chunk in stream:
        data += chunk
        jpg_start = data.find(b'\xff\xd8')
        jpg_end = data.find(b'\xff\xd9')
        if jpg_start != -1 and jpg_end != -1:
            jpg = data[jpg_start:jpg_end + 2]
            return jpg


class YiCamera(Camera):
    """Define an implementation of a Yi Camera."""

    def __init__(self, hass, config):
        """Initialize."""
        super().__init__()
        self.hass = hass
        self.host = config.get(CONF_HOST)
        self.passwd = config.get(CONF_PASSWORD)
        self.user = config.get(CONF_USERNAME)

    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        import aioftp

        client = aioftp.Client()
        yield from client.connect(self.host)
        yield from client.login(self.user, self.passwd)
        _LOGGER.debug('AARON')
