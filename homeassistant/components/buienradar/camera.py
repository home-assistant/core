"""Provide animated GIF loops of Buienradar imagery."""
import aiohttp
import asyncio
import logging
import voluptuous as vol

from datetime import timedelta
from typing import Optional

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import CONF_ID, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from homeassistant.util import dt as dt_util

CONF_DIMENSION = 'dimension'
CONF_INTERVAL = 'interval'

RADAR_MAP_URL_TEMPLATE = ('https://api.buienradar.nl/image/1.0/'
                          'RadarMapNL?w={w}&h={h}')

_LOG = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend({
        vol.Optional(CONF_DIMENSION): cv.positive_int,
        vol.Optional(CONF_INTERVAL): cv.positive_int,
        vol.Optional(CONF_NAME): cv.string,
    }))


async def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up buienradar radar-loop camera component."""
    c_id = config.get(CONF_ID)
    dimension = config.get(CONF_DIMENSION) or 512
    interval = config.get(CONF_INTERVAL) or 600 
    name = config.get(CONF_NAME) or "Buienradar Radar Loop"

    async_add_entities([BuienradarCam(hass, name, c_id, dimension, interval)])


class BuienradarCam(Camera):
    _dimension: int
    """ Deadline for image refresh """
    _deadline: Optional[int]
    _name: str
    _interval: Optional[int]
    """
    A camera component producing animated buienradar radar-imagery GIFs.

    Image URL taken from https://www.buienradar.nl/overbuienradar/gratis-weerdata
    """

    def __init__(self, hass, name: str, c_id: Optional[str], dimension: int, interval: Optional[int]):
        """Initialize the component."""
        super().__init__()
        self._hass = hass
        self._name = name

        self._dimension = dimension
        self._interval = interval

        self._lock = asyncio.Lock(loop=hass.loop)

        self._last_image = None
        # deadline for image to be refreshed
        self._deadline = None

    @property
    def name(self):
        """Return the component name."""
        return self._name

    # Cargo-cult from components/proxy/camera.py
    def camera_image(self):
        """Return camera image."""
        return run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop).result()

    def __needs_refresh(self) -> bool:
        if not (self._interval and self._deadline and self._last_image):
            _LOG.info("refresh due to preconditions")
            return True

        if dt_util.utcnow() > self._deadline:
            _LOG.info("refresh due to refresh interval")
        return dt_util.utcnow() > self._deadline

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        if not self.__needs_refresh():
            _LOG.info(f"r: cached image {self._deadline}, {self._interval}")
            return self._last_image

        async with self._lock:
            # check if image was loaded while locked
            if not self.__needs_refresh():
                _LOG.info(f"return fresh cached image {self._deadline}, "
                         f"{self._interval}")
                return self._last_image

            _LOG.info(f"getting new image.")

            # deadline has passed, get shared ClientSession to load new image.
            # note that this session dies when another component (i.e. aiohue)
            # throws.
            session: asyncio.ClientSession = async_get_clientsession(self._hass)

            now = dt_util.utcnow()
            url = RADAR_MAP_URL_TEMPLATE.format(w=self._dimension,
                                                h=self._dimension)
            try:
                async with session.get(url, timeout=5) as res:
                    if res.status != 200:
                        _LOG.error("Failed to fetch image, %s", res.status)
                    else:
                        self._last_image = await res.read()
                        self._deadline = now + timedelta(seconds=self._interval)
                        _LOG.info(f"return newly loaded image, deadline: {self._deadline}, {self._interval}")
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                _LOG.error("Failed to fetch image, %s", type(e))

            return self._last_image
