"""
Support for IP Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.generic/
"""
import asyncio
import logging

import aiohttp
import async_timeout
import requests
from requests.auth import HTTPDigestAuth
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_AUTHENTICATION,
    HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION)
from homeassistant.exceptions import TemplateError
from homeassistant.components.camera import (PLATFORM_SCHEMA, Camera)
from homeassistant.helpers import config_validation as cv
from homeassistant.util.async import run_coroutine_threadsafe

_LOGGER = logging.getLogger(__name__)

CONF_LIMIT_REFETCH_TO_URL_CHANGE = 'limit_refetch_to_url_change'
CONF_STILL_IMAGE_URL = 'still_image_url'

DEFAULT_NAME = 'Generic Camera'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STILL_IMAGE_URL): cv.template,
    vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION):
        vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
    vol.Optional(CONF_LIMIT_REFETCH_TO_URL_CHANGE, default=False): cv.boolean,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
})


@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup a generic IP Camera."""
    hass.loop.create_task(async_add_devices([GenericCamera(hass, config)]))


# pylint: disable=too-many-instance-attributes
class GenericCamera(Camera):
    """A generic implementation of an IP camera."""

    def __init__(self, hass, device_info):
        """Initialize a generic camera."""
        super().__init__()
        self.hass = hass
        self._authentication = device_info.get(CONF_AUTHENTICATION)
        self._name = device_info.get(CONF_NAME)
        self._still_image_url = device_info[CONF_STILL_IMAGE_URL]
        self._still_image_url.hass = hass
        self._limit_refetch = device_info[CONF_LIMIT_REFETCH_TO_URL_CHANGE]

        username = device_info.get(CONF_USERNAME)
        password = device_info.get(CONF_PASSWORD)

        if username and password:
            if self._authentication == HTTP_DIGEST_AUTHENTICATION:
                self._auth = HTTPDigestAuth(username, password)
            else:
                self._auth = aiohttp.BasicAuth(username, password=password)
        else:
            self._auth = None

        self._last_url = None
        self._last_image = None
        self._session = aiohttp.ClientSession(loop=hass.loop, auth=self._auth)

    def camera_image(self):
        """Return bytes of camera image."""
        return run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop).result()

    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        try:
            url = self._still_image_url.async_render()
        except TemplateError as err:
            _LOGGER.error('Error parsing template %s: %s',
                          self._still_image_url, err)
            return self._last_image

        if url == self._last_url and self._limit_refetch:
            return self._last_image

        # aiohttp don't support DigestAuth jet
        if self._authentication == HTTP_DIGEST_AUTHENTICATION:
            def fetch():
                """Read image from a URL."""
                try:
                    kwargs = {'timeout': 10, 'auth': self._auth}
                    response = requests.get(url, **kwargs)
                    return response.content
                except requests.exceptions.RequestException as error:
                    _LOGGER.error('Error getting camera image: %s', error)
                    return self._last_image

            self._last_image = yield from self.hass.loop.run_in_executor(
                None, fetch)
        # async
        else:
            try:
                with async_timeout.timeout(10, loop=self.hass.loop):
                    respone = yield from self._session.get(url)
                    self._last_image = yield from respone.read()
                    self.hass.loop.create_task(respone.release())
            except asyncio.TimeoutError:
                _LOGGER.error('Timeout getting camera image')
                return self._last_image

        self._last_url = url
        return self._last_image

    @property
    def name(self):
        """Return the name of this device."""
        return self._name
