"""
Support for viewing the camera feed from a DoorBird video doorbell.
"""

import aiohttp
import asyncio
import async_timeout
import datetime
import logging
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.components.doorbird import DOMAIN
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.async import run_coroutine_threadsafe

DEPENDENCIES = ['doorbird']

_CAMERA_LIVE = "DoorBird Live"
_CAMERA_LAST_VISITOR = "DoorBird Last Ring"
_LIVE_INTERVAL = datetime.timedelta(seconds=1)
_LAST_VISITOR_INTERVAL = datetime.timedelta(minutes=1)
_LOGGER = logging.getLogger(__name__)
_TIMEOUT = 10  # seconds

CONF_SHOW_LAST_VISITOR = 'last_visitor'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SHOW_LAST_VISITOR, default=False): cv.boolean
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    device = hass.data.get(DOMAIN)

    _LOGGER.debug("Adding DoorBird camera " + _CAMERA_LIVE)
    entities = [DoorBirdCamera(hass, device.live_image_url, _CAMERA_LIVE,
                               _LIVE_INTERVAL)]

    if config.get(CONF_SHOW_LAST_VISITOR):
        _LOGGER.debug("Adding DoorBird camera " + _CAMERA_LAST_VISITOR)
        entities.append(DoorBirdCamera(hass, device.history_image_url(1),
                                       _CAMERA_LAST_VISITOR,
                                       _LAST_VISITOR_INTERVAL))

    async_add_devices(entities)
    _LOGGER.info("Added DoorBird camera(s)")
    return True


class DoorBirdCamera(Camera):
    def __init__(self, hass, url, name, interval=None):
        """Initialize the camera on a DoorBird device."""
        self._hass = hass
        self._url = url
        self._name = name
        self._last_image = None
        self._interval = interval or datetime.timedelta
        self._last_update = datetime.datetime.min
        super().__init__()

    @property
    def name(self):
        """:returns: The name of the camera."""
        return self._name

    def camera_image(self):
        """:returns: The bytes of a camera image."""
        return run_coroutine_threadsafe(
            self.async_camera_image(), self._hass.loop).result()

    @asyncio.coroutine
    def async_camera_image(self):
        """:returns: A still image from the camera."""

        now = datetime.datetime.now()

        if self._last_image and now - self._last_update < self._interval:
            return self._last_image

        try:
            websession = async_get_clientsession(self._hass)

            with async_timeout.timeout(_TIMEOUT, loop=self._hass.loop):
                response = yield from websession.get(self._url)

            self._last_image = yield from response.read()
            self._last_update = now
            return self._last_image
        except asyncio.TimeoutError:
            _LOGGER.error("Camera image timed out")
            return self._last_image
        except aiohttp.ClientError as error:
            _LOGGER.error("Error getting camera image: %s", error)
            return self._last_image
