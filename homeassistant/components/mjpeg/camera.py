"""Support for IP Cameras."""
from __future__ import annotations

import asyncio
from contextlib import closing
import logging

import aiohttp
import async_timeout
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_web,
    async_get_clientsession,
)

_LOGGER = logging.getLogger(__name__)

CONF_MJPEG_URL = "mjpeg_url"
CONF_STILL_IMAGE_URL = "still_image_url"
CONTENT_TYPE_HEADER = "Content-Type"

DEFAULT_NAME = "Mjpeg Camera"
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MJPEG_URL): cv.url,
        vol.Optional(CONF_STILL_IMAGE_URL): cv.url,
        vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a MJPEG IP Camera."""
    filter_urllib3_logging()

    if discovery_info:
        config = PLATFORM_SCHEMA(discovery_info)
    async_add_entities([MjpegCamera(config)])


def filter_urllib3_logging():
    """Filter header errors from urllib3 due to a urllib3 bug."""
    urllib3_logger = logging.getLogger("urllib3.connectionpool")
    if not any(isinstance(x, NoHeaderErrorFilter) for x in urllib3_logger.filters):
        urllib3_logger.addFilter(NoHeaderErrorFilter())


def extract_image_from_mjpeg(stream):
    """Take in a MJPEG stream object, return the jpg from it."""
    data = b""

    for chunk in stream:
        data += chunk
        jpg_end = data.find(b"\xff\xd9")

        if jpg_end == -1:
            continue

        jpg_start = data.find(b"\xff\xd8")

        if jpg_start == -1:
            continue

        return data[jpg_start : jpg_end + 2]


class MjpegCamera(Camera):
    """An implementation of an IP camera that is reachable over a URL."""

    def __init__(self, device_info):
        """Initialize a MJPEG camera."""
        super().__init__()
        self._name = device_info.get(CONF_NAME)
        self._authentication = device_info.get(CONF_AUTHENTICATION)
        self._username = device_info.get(CONF_USERNAME)
        self._password = device_info.get(CONF_PASSWORD)
        self._mjpeg_url = device_info[CONF_MJPEG_URL]
        self._still_image_url = device_info.get(CONF_STILL_IMAGE_URL)

        self._auth = None
        if (
            self._username
            and self._password
            and self._authentication == HTTP_BASIC_AUTHENTICATION
        ):
            self._auth = aiohttp.BasicAuth(self._username, password=self._password)
        self._verify_ssl = device_info.get(CONF_VERIFY_SSL)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        # DigestAuth is not supported
        if (
            self._authentication == HTTP_DIGEST_AUTHENTICATION
            or self._still_image_url is None
        ):
            image = await self.hass.async_add_executor_job(self.camera_image)
            return image

        websession = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        try:
            with async_timeout.timeout(10):
                response = await websession.get(self._still_image_url, auth=self._auth)

                image = await response.read()
                return image

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting camera image from %s", self._name)

        except aiohttp.ClientError as err:
            _LOGGER.error("Error getting new camera image from %s: %s", self._name, err)

        return None

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        if self._username and self._password:
            if self._authentication == HTTP_DIGEST_AUTHENTICATION:
                auth: HTTPDigestAuth | HTTPBasicAuth = HTTPDigestAuth(
                    self._username, self._password
                )
            else:
                auth = HTTPBasicAuth(self._username, self._password)
            req = requests.get(
                self._mjpeg_url,
                auth=auth,
                stream=True,
                timeout=10,
                verify=self._verify_ssl,
            )
        else:
            req = requests.get(self._mjpeg_url, stream=True, timeout=10)

        with closing(req) as response:
            return extract_image_from_mjpeg(response.iter_content(102400))

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        # aiohttp don't support DigestAuth -> Fallback
        if self._authentication == HTTP_DIGEST_AUTHENTICATION:
            return await super().handle_async_mjpeg_stream(request)

        # connect to stream
        websession = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        stream_coro = websession.get(self._mjpeg_url, auth=self._auth)

        return await async_aiohttp_proxy_web(self.hass, request, stream_coro)

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name


class NoHeaderErrorFilter(logging.Filter):
    """Filter out urllib3 Header Parsing Errors due to a urllib3 bug."""

    def filter(self, record):
        """Filter out Header Parsing Errors."""
        return "Failed to parse headers" not in record.getMessage()
