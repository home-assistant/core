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
    HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION, CONF_VERIFY_SSL)
from homeassistant.exceptions import TemplateError
from homeassistant.components.camera import (
    PLATFORM_SCHEMA, DEFAULT_CONTENT_TYPE, Camera)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.util.async_ import run_coroutine_threadsafe

_LOGGER = logging.getLogger(__name__)

CONF_CONTENT_TYPE = 'content_type'
CONF_LIMIT_REFETCH_TO_URL_CHANGE = 'limit_refetch_to_url_change'
CONF_STILL_IMAGE_URL = 'still_image_url'
CONF_FRAMERATE = 'framerate'

DEFAULT_NAME = 'Generic Camera'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STILL_IMAGE_URL): cv.template,
    vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION):
        vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
    vol.Optional(CONF_LIMIT_REFETCH_TO_URL_CHANGE, default=False): cv.boolean,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_CONTENT_TYPE, default=DEFAULT_CONTENT_TYPE): cv.string,
    vol.Optional(CONF_FRAMERATE, default=2): cv.positive_int,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up a generic IP Camera."""
    async_add_entities([GenericCamera(hass, config)])


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
        self._frame_interval = 1 / device_info[CONF_FRAMERATE]
        self.content_type = device_info[CONF_CONTENT_TYPE]
        self.verify_ssl = device_info[CONF_VERIFY_SSL]

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

    @property
    def frame_interval(self):
        """Return the interval between frames of the mjpeg stream."""
        return self._frame_interval

    def camera_image(self):
        """Return bytes of camera image."""
        return run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop).result()

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        try:
            url = self._still_image_url.async_render()
        except TemplateError as err:
            _LOGGER.error(
                "Error parsing template %s: %s", self._still_image_url, err)
            return self._last_image

        if url == self._last_url and self._limit_refetch:
            return self._last_image

        # aiohttp don't support DigestAuth yet
        if self._authentication == HTTP_DIGEST_AUTHENTICATION:
            def fetch():
                """Read image from a URL."""
                try:
                    response = requests.get(url, timeout=10, auth=self._auth,
                                            verify=self.verify_ssl)
                    return response.content
                except requests.exceptions.RequestException as error:
                    _LOGGER.error("Error getting camera image: %s", error)
                    return self._last_image

            self._last_image = await self.hass.async_add_job(
                fetch)
        # async
        else:
            try:
                websession = async_get_clientsession(
                    self.hass, verify_ssl=self.verify_ssl)
                with async_timeout.timeout(10, loop=self.hass.loop):
                    response = await websession.get(
                        url, auth=self._auth)
                self._last_image = await response.read()
            except asyncio.TimeoutError:
                _LOGGER.error("Timeout getting camera image")
                return self._last_image
            except aiohttp.ClientError as err:
                _LOGGER.error("Error getting new camera image: %s", err)
                return self._last_image

        self._last_url = url
        return self._last_image

    @property
    def name(self):
        """Return the name of this device."""
        return self._name
