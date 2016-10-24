"""
Support for IP Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.mjpeg/
"""
import asyncio
import logging
from contextlib import closing

import aiohttp
from aiohttp import web
from aiohttp.web_exceptions import HTTPGatewayTimeout
import async_timeout
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_AUTHENTICATION,
    HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION)
from homeassistant.components.camera import (PLATFORM_SCHEMA, Camera)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_MJPEG_URL = 'mjpeg_url'
CONTENT_TYPE_HEADER = 'Content-Type'

DEFAULT_NAME = 'Mjpeg Camera'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MJPEG_URL): cv.url,
    vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION):
        vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
})


@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup a MJPEG IP Camera."""
    hass.loop.create_task(async_add_devices([MjpegCamera(hass, config)]))


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


# pylint: disable=too-many-instance-attributes
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

        auth = None
        if self._authentication == HTTP_BASIC_AUTHENTICATION:
            auth = aiohttp.BasicAuth(self._username, password=self._password)

        self._session = aiohttp.ClientSession(loop=hass.loop, auth=auth)

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
        try:
            with async_timeout.timeout(10, loop=self.hass.loop):
                stream = yield from self._session.get(self._mjpeg_url)
        except asyncio.TimeoutError:
            raise HTTPGatewayTimeout()

        response = web.StreamResponse()
        response.content_type = stream.headers.get(CONTENT_TYPE_HEADER)
        response.enable_chunked_encoding()

        yield from response.prepare(request)

        try:
            while True:
                data = yield from stream.content.read(102400)
                if not data:
                    break
                response.write(data)
        finally:
            self.hass.loop.create_task(stream.release())
            self.hass.loop.create_task(response.write_eof())

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
