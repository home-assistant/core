"""Support for viewing the camera feed from a DoorBird video doorbell."""

import asyncio
import datetime
import logging
import voluptuous as vol

import aiohttp
import async_timeout

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.components.doorbird import DOMAIN as DOORBIRD_DOMAIN
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

DEPENDENCIES = ['doorbird']

_CAMERA_LIVE = "DoorBird Live"
_CAMERA_LAST_VISITOR = "DoorBird Last Ring"
_LIVE_INTERVAL = datetime.timedelta(seconds=1)
_LAST_VISITOR_INTERVAL = datetime.timedelta(minutes=1)
_LOGGER = logging.getLogger(__name__)
_TIMEOUT = 10  # seconds

CONF_SHOW_LAST_VISITOR = 'last_visitor'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SHOW_LAST_VISITOR, default=False): cv.boolean
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the DoorBird camera platform."""
    device = hass.data.get(DOORBIRD_DOMAIN)

    _LOGGER.debug("Adding DoorBird camera %s", _CAMERA_LIVE)
    entities = [DoorBirdCamera(device.live_image_url, _CAMERA_LIVE,
                               _LIVE_INTERVAL)]

    if config.get(CONF_SHOW_LAST_VISITOR):
        _LOGGER.debug("Adding DoorBird camera %s", _CAMERA_LAST_VISITOR)
        entities.append(DoorBirdCamera(device.history_image_url(1),
                                       _CAMERA_LAST_VISITOR,
                                       _LAST_VISITOR_INTERVAL))

    async_add_devices(entities)
    _LOGGER.info("Added DoorBird camera(s)")


class DoorBirdCamera(Camera):
    """The camera on a DoorBird device."""

    def __init__(self, url, name, interval=None):
        """Initialize the camera on a DoorBird device."""
        self._url = url
        self._name = name
        self._last_image = None
        self._interval = interval or datetime.timedelta
        self._last_update = datetime.datetime.min
        super().__init__()

    @property
    def name(self):
        """Get the name of the camera."""
        return self._name

    @asyncio.coroutine
    def async_camera_image(self):
        """Pull a still image from the camera."""
        now = datetime.datetime.now()

        if self._last_image and now - self._last_update < self._interval:
            return self._last_image

        try:
            websession = async_get_clientsession(self.hass)

            with async_timeout.timeout(_TIMEOUT, loop=self.hass.loop):
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
