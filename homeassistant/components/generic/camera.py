"""Support for IP Cameras."""
import asyncio
import logging

import httpx
import voluptuous as vol

from homeassistant.components.camera import (
    DEFAULT_CONTENT_TYPE,
    PLATFORM_SCHEMA,
    SUPPORT_STREAM,
    Camera,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.reload import async_setup_reload_service

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONF_CONTENT_TYPE = "content_type"
CONF_LIMIT_REFETCH_TO_URL_CHANGE = "limit_refetch_to_url_change"
CONF_STILL_IMAGE_URL = "still_image_url"
CONF_STREAM_SOURCE = "stream_source"
CONF_FRAMERATE = "framerate"
CONF_RTSP_TRANSPORT = "rtsp_transport"
FFMPEG_OPTION_MAP = {CONF_RTSP_TRANSPORT: "rtsp_transport"}
ALLOWED_RTSP_TRANSPORT_PROTOCOLS = {"tcp", "udp", "udp_multicast", "http"}

DEFAULT_NAME = "Generic Camera"
GET_IMAGE_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STILL_IMAGE_URL): cv.template,
        vol.Optional(CONF_STREAM_SOURCE): cv.template,
        vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_LIMIT_REFETCH_TO_URL_CHANGE, default=False): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_CONTENT_TYPE, default=DEFAULT_CONTENT_TYPE): cv.string,
        vol.Optional(CONF_FRAMERATE, default=2): vol.Any(
            cv.small_float, cv.positive_int
        ),
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_RTSP_TRANSPORT): vol.In(ALLOWED_RTSP_TRANSPORT_PROTOCOLS),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a generic IP Camera."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

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
        self._stream_source = device_info.get(CONF_STREAM_SOURCE)
        self._still_image_url.hass = hass
        if self._stream_source is not None:
            self._stream_source.hass = hass
        self._limit_refetch = device_info[CONF_LIMIT_REFETCH_TO_URL_CHANGE]
        self._frame_interval = 1 / device_info[CONF_FRAMERATE]
        self._supported_features = SUPPORT_STREAM if self._stream_source else 0
        self.content_type = device_info[CONF_CONTENT_TYPE]
        self.verify_ssl = device_info[CONF_VERIFY_SSL]
        if device_info.get(CONF_RTSP_TRANSPORT):
            self.stream_options[FFMPEG_OPTION_MAP[CONF_RTSP_TRANSPORT]] = device_info[
                CONF_RTSP_TRANSPORT
            ]

        username = device_info.get(CONF_USERNAME)
        password = device_info.get(CONF_PASSWORD)

        if username and password:
            if self._authentication == HTTP_DIGEST_AUTHENTICATION:
                self._auth = httpx.DigestAuth(username=username, password=password)
            else:
                self._auth = httpx.BasicAuth(username=username, password=password)
        else:
            self._auth = None

        self._last_url = None
        self._last_image = None

    @property
    def supported_features(self):
        """Return supported features for this camera."""
        return self._supported_features

    @property
    def frame_interval(self):
        """Return the interval between frames of the mjpeg stream."""
        return self._frame_interval

    def camera_image(self):
        """Return bytes of camera image."""
        return asyncio.run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop
        ).result()

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        try:
            url = self._still_image_url.async_render(parse_result=False)
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._still_image_url, err)
            return self._last_image

        if url == self._last_url and self._limit_refetch:
            return self._last_image

        try:
            async_client = get_async_client(self.hass, verify_ssl=self.verify_ssl)
            response = await async_client.get(
                url, auth=self._auth, timeout=GET_IMAGE_TIMEOUT
            )
            response.raise_for_status()
            self._last_image = response.content
        except httpx.TimeoutException:
            _LOGGER.error("Timeout getting camera image from %s", self._name)
            return self._last_image
        except (httpx.RequestError, httpx.HTTPStatusError) as err:
            _LOGGER.error("Error getting new camera image from %s: %s", self._name, err)
            return self._last_image

        self._last_url = url
        return self._last_image

    @property
    def name(self):
        """Return the name of this device."""
        return self._name

    async def stream_source(self):
        """Return the source of the stream."""
        if self._stream_source is None:
            return None

        try:
            return self._stream_source.async_render(parse_result=False)
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._stream_source, err)
            return None
