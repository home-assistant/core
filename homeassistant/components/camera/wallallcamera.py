"""
Support for wall all web camera, pretty much just a copy of the mjpg camera
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

HOST = 'host'

CONTENT_TYPE_HEADER = 'Content-Type'

DEFAULT_NAME = 'WallAll Camera'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(HOST): cv.url,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a Wallall IP Camera."""
    if discovery_info:
        config = PLATFORM_SCHEMA(discovery_info)
    async_add_devices([WallAllCamera(hass, config)])


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


class WallAllCamera(Camera):
    """An implementation of an IP camera that is reachable over a URL."""

    def __init__(self, hass, device_info):
        """Initialize a MJPEG camera."""
        super().__init__()
        self._name = device_info.get(CONF_NAME)
        self._host = device_info[HOST]


    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        image = yield from self.hass.async_add_job(
            self.camera_image)
        return image

    def camera_image(self):
        """Return a still image response from the camera."""
        req = requests.get(self._host, stream=True, timeout=10)
        with closing(req) as response:
            return extract_image_from_mjpeg(response.iter_content(102400))

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        # connect to stream
        websession = async_get_clientsession(self.hass)
        stream_coro = websession.get(self._host, auth=self._auth)

        yield from async_aiohttp_proxy_web(self.hass, request, stream_coro)

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
