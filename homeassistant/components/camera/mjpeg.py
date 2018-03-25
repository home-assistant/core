"""
Support for IP Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.mjpeg/
"""
import asyncio
import logging
from contextlib import closing

import aiohttp
import async_timeout
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_AUTHENTICATION,
    HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION)
from homeassistant.components.camera import (PLATFORM_SCHEMA, Camera)
from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession, async_aiohttp_proxy_web)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_MJPEG_URL = 'mjpeg_url'
CONF_STILL_IMAGE_URL = 'still_image_url'
CONTENT_TYPE_HEADER = 'Content-Type'

DEFAULT_NAME = 'Mjpeg Camera'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MJPEG_URL): cv.url,
    vol.Optional(CONF_STILL_IMAGE_URL): cv.url,
    vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION):
        vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
})


@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a MJPEG IP Camera."""
    if discovery_info:
        config = PLATFORM_SCHEMA(discovery_info)
    async_add_devices([MjpegCamera(hass, config)])


def extract_image_from_mjpeg(stream):
    """Take in a MJPEG stream object, return the jpg from it."""
    data = b''
    for chunk in stream:
        data += chunk
        jpg_start = data.find(b'\xff\xd8')
        jpg_end = data.find(b'\xff\xd9')
        if jpg_start != -1 and jpg_end != -1:
            jpg = data[jpg_start:jpg_end + 2]
            return jpg


class MjpegCamera(Camera):
    """An implementation of an IP camera that is reachable over a URL."""

    def __init__(self, hass, device_info):
        """Initialize a MJPEG camera."""
        super().__init__()
        self._name = device_info.get(CONF_NAME)
        self._authentication = device_info.get(CONF_AUTHENTICATION)
        self._username = device_info.get(CONF_USERNAME)
        self._password = device_info.get(CONF_PASSWORD)
        self._mjpeg_url = device_info[CONF_MJPEG_URL]
        self._still_image_url = device_info.get(CONF_STILL_IMAGE_URL)

        self._auth = None
        if self._username and self._password:
            if self._authentication == HTTP_BASIC_AUTHENTICATION:
                self._auth = aiohttp.BasicAuth(
                    self._username, password=self._password
                )

    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        # DigestAuth is not supported
        if self._authentication == HTTP_DIGEST_AUTHENTICATION or \
           self._still_image_url is None:
            image = yield from self.hass.async_add_job(
                self.camera_image)
            return image

        websession = async_get_clientsession(self.hass)
        try:
            with async_timeout.timeout(10, loop=self.hass.loop):
                response = yield from websession.get(
                    self._still_image_url, auth=self._auth)

                image = yield from response.read()
                return image

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting camera image")

        except aiohttp.ClientError as err:
            _LOGGER.error("Error getting new camera image: %s", err)

    def camera_image(self):
        """Return a still image response from the camera."""
        if self._username and self._password:
            if self._authentication == HTTP_DIGEST_AUTHENTICATION:
                auth = HTTPDigestAuth(self._username, self._password)
            else:
                auth = HTTPBasicAuth(self._username, self._password)
            req = requests.get(
                self._mjpeg_url, auth=auth, stream=True, timeout=10)
        else:
            req = requests.get(self._mjpeg_url, stream=True, timeout=10)

        # https://github.com/PyCQA/pylint/issues/1437
        # pylint: disable=no-member
        with closing(req) as response:
            return extract_image_from_mjpeg(response.iter_content(102400))

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        # aiohttp don't support DigestAuth -> Fallback
        if self._authentication == HTTP_DIGEST_AUTHENTICATION:
            yield from super().handle_async_mjpeg_stream(request)
            return

        # connect to stream
        websession = async_get_clientsession(self.hass)
        stream_coro = websession.get(self._mjpeg_url, auth=self._auth)

        yield from async_aiohttp_proxy_web(self.hass, request, stream_coro)

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
