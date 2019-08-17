"""Support for Vivotek IP Cameras."""
import asyncio
import logging

import aiohttp
import async_timeout
import requests
from requests.auth import HTTPBasicAuth
from requests.auth import HTTPDigestAuth
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_AUTHENTICATION,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    CONF_VERIFY_SSL,
    CONF_IP_ADDRESS,
)
from homeassistant.exceptions import TemplateError
from homeassistant.components.camera import (
    PLATFORM_SCHEMA,
    DEFAULT_CONTENT_TYPE,
    SUPPORT_STREAM,
    Camera,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.util.async_ import run_coroutine_threadsafe

_LOGGER = logging.getLogger(__name__)

CONF_CONTENT_TYPE = "content_type"
CONF_LIMIT_REFETCH_TO_URL_CHANGE = "limit_refetch_to_url_change"
CONF_STILL_IMAGE_URL = "still_image_url"
CONF_STREAM_SOURCE = "stream_source"
CONF_FRAMERATE = "framerate"

DEFAULT_NAME = "Vivotek Camera"
DEFAULT_EVENT_0_KEY = "event_i0_enable"
DEFAULT_PARAM_PATHS = {
    "get": "/cgi-bin/admin/getparam.cgi",
    "set": "/cgi-bin/admin/setparam.cgi",
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STILL_IMAGE_URL): cv.template,
        vol.Optional(CONF_STREAM_SOURCE, default=None): vol.Any(None, cv.string),
        vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_LIMIT_REFETCH_TO_URL_CHANGE, default=False): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_CONTENT_TYPE, default=DEFAULT_CONTENT_TYPE): cv.string,
        vol.Optional(CONF_FRAMERATE, default=2): cv.positive_int,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Required(CONF_IP_ADDRESS): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a generic IP Camera."""
    async_add_entities([VivotekCamera(hass, config)])


class VivotekCamera(Camera):
    """A Vivotek IP camera."""

    def __init__(self, hass, device_info):
        """Initialize a generic camera."""
        super().__init__()
        self.hass = hass
        self._authentication = device_info.get(CONF_AUTHENTICATION)
        self._name = device_info.get(CONF_NAME)
        self._still_image_url = device_info[CONF_STILL_IMAGE_URL]
        self._stream_source = device_info[CONF_STREAM_SOURCE]
        self._still_image_url.hass = hass
        self._limit_refetch = device_info[CONF_LIMIT_REFETCH_TO_URL_CHANGE]
        self._frame_interval = 1 / device_info[CONF_FRAMERATE]
        self._supported_features = SUPPORT_STREAM if self._stream_source else 0
        self.content_type = device_info[CONF_CONTENT_TYPE]
        self.verify_ssl = device_info[CONF_VERIFY_SSL]
        self._event_i0_status = None
        self._event_0_key = DEFAULT_EVENT_0_KEY
        self._ip = device_info.get(CONF_IP_ADDRESS)
        self._get_param_url = "http://" + self._ip + DEFAULT_PARAM_PATHS["get"]
        self._set_param_url = "http://" + self._ip + DEFAULT_PARAM_PATHS["set"]
        username = device_info.get(CONF_USERNAME)
        password = device_info.get(CONF_PASSWORD)

        if username and password:
            if self._authentication == HTTP_DIGEST_AUTHENTICATION:
                self._auth = HTTPDigestAuth(username, password)
            else:
                self._auth = aiohttp.BasicAuth(username, password=password)
                self._requests_auth = HTTPBasicAuth(username, password)
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

    async def async_event_enabled(self, event_key):
        """Return true if event for the provided key is enabled."""
        value = await self.async_get_param(event_key)
        return int(value.replace("'", "")) == 1

    def event_enabled(self, event_key):
        """Return true if event for the provided key is enabled."""
        response = self.get_param(event_key)
        # _LOGGER.debug("Vivotek camera response: %s", response)
        return int(response.replace("'", "")) == 1

    # async def async_get_param(self, param):
    #     """Return the value of the provided key."""
    #     try:
    #         websession = async_get_clientsession(
    #             self.hass, verify_ssl=self.verify_ssl
    #         )
    #         with async_timeout.timeout(10):
    #             response = await websession.get(
    #                 self._get_param_url,
    #                 auth=self._auth,
    #                 params={param},
    #             )
    #         text = await response.text()
    #         _LOGGER.info("Vivotek camera GET response text: %s", text)
    #         return text.strip().split("=")[1]
    #     except asyncio.TimeoutError:
    #         _LOGGER.error("Timeout getting Vivotek camera parameter: %s", self._name)
    #     except aiohttp.ClientError as err:
    #         _LOGGER.error("Error getting Vivotek camera parameter: %s", err)

    async def async_set_param(self, param, value):
        """Set the value of the provided key."""
        try:
            websession = async_get_clientsession(self.hass, verify_ssl=self.verify_ssl)
            with async_timeout.timeout(10):
                response = await websession.post(
                    self._set_param_url, auth=self._auth, data={param: value}
                )
            text = await response.text()
            _LOGGER.info("Vivotek camera SET response text: %s", text)
            return text.strip().split("=")[1]
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout setting Vivotek camera parameter: %s", self._name)
        except aiohttp.ClientError as err:
            _LOGGER.error("Error setting Vivotek camera parameter: %s", err)

    def get_param(self, param):
        """Return the value of the provided key."""
        try:
            response = requests.get(
                self._get_param_url,
                auth=self._requests_auth,
                params=(param),
                timeout=10,
                verify=self.verify_ssl,
            )
            return response.content.decode("utf-8").strip().split("=")[1]
        except requests.exceptions.RequestException as error:
            _LOGGER.error("Error getting Vivotek camera parameter: %s", error)

    # def set_param(self, param, value):
    #     """Set the value of the provided key."""
    #     try:
    #         response = requests.post(
    #             self._set_param_url, auth=self._requests_auth, data={param: value}
    #         )
    #         return response.content.decode("utf-8").strip().split("=")[1]
    #     except requests.exceptions.RequestException as error:
    #         _LOGGER.error("Error setting Vivotek camera parameter: %s", error)

    def camera_image(self):
        """Return bytes of camera image."""
        return run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop
        ).result()

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        try:
            url = self._still_image_url.async_render()
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._still_image_url, err)
            return self._last_image

        if url == self._last_url and self._limit_refetch:
            return self._last_image

        # aiohttp don't support DigestAuth yet
        if self._authentication == HTTP_DIGEST_AUTHENTICATION:

            def fetch():
                """Read image from a URL."""
                try:
                    response = requests.get(
                        url, timeout=10, auth=self._auth, verify=self.verify_ssl
                    )
                    return response.content
                except requests.exceptions.RequestException as error:
                    _LOGGER.error("Error getting camera image: %s", error)
                    return self._last_image

            self._last_image = await self.hass.async_add_job(fetch)
        # async
        else:
            try:
                websession = async_get_clientsession(
                    self.hass, verify_ssl=self.verify_ssl
                )
                with async_timeout.timeout(10):
                    response = await websession.get(url, auth=self._auth)
                self._last_image = await response.read()
            except asyncio.TimeoutError:
                _LOGGER.error("Timeout getting image from: %s", self._name)
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

    async def stream_source(self):
        """Return the source of the stream."""
        return self._stream_source

    @property
    def motion_detection_enabled(self):
        return self.event_enabled(self._event_0_key)

    async def enable_motion_detection(self):
        """Enable motion detection in camera."""
        await self.async_set_param(self._event_0_key, 1)

    async def disable_motion_detection(self):
        """Disable motion detection in camera."""
        # self.set_param(self._event_0_key, 0)
        await self.async_set_param(self._event_0_key, 0)
