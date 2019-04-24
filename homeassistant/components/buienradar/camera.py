"""Provide animated GIF loops of Buienradar imagery."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import CONF_ID, CONF_NAME

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import run_coroutine_threadsafe

CONF_DIMENSION = 'dimension'
CONF_DELTA = 'delta'

RADAR_MAP_URL_TEMPLATE = ('https://api.buienradar.nl/image/1.0/'
                          'RadarMapNL?w={w}&h={h}')

_LOG = logging.getLogger(__name__)

# Maximum range according to docs
DIM_RANGE = vol.All(vol.Coerce(int), vol.Range(min=120, max=700))

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend({
        vol.Optional(CONF_DIMENSION): DIM_RANGE,
        vol.Optional(CONF_DELTA): vol.All(vol.Coerce(float),
                                             vol.Range(min=0)),
        vol.Optional(CONF_NAME): cv.string,
    }))


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up buienradar radar-loop camera component."""
    c_id = config.get(CONF_ID)
    dimension = config.get(CONF_DIMENSION) or 512
    delta = config.get(CONF_DELTA) or 600.0
    name = config.get(CONF_NAME) or "Buienradar loop"

    async_add_entities([BuienradarCam(hass, name, c_id, dimension, delta)])


class BuienradarCam(Camera):
    """
    A camera component producing animated buienradar radar-imagery GIFs.

    Rain radar imagery camera based on image URL taken from [0].

    [0]: https://www.buienradar.nl/overbuienradar/gratis-weerdata
    """

    _dimension = 0          # type: int
    """ Deadline for image refresh """
    _deadline = None        # type: Optional[datetime]
    _name = ""              # type: str
    _delta = 0.0         # type: float
    _condition = None       # type: Optional[asyncio.Condition]
    """ Loading status """
    _loading = False        # type: bool

    _last_image = None      # type: Optional[bytes]
    """ last modified HTTP response header"""
    _last_modified = None   # type: Optional[str]

    def __init__(self, hass, name: str, c_id: Optional[str], dimension: int,
                 delta: float):
        """Initialize the component."""
        super().__init__()
        self._hass = hass
        self._name = name

        self._dimension = dimension
        self._delta = delta

        self._condition = asyncio.Condition(loop=hass.loop)

        self._last_image = None
        self._last_modified = None
        self._loading = False
        # deadline for image to be refreshed
        self._deadline = None

    @property
    def name(self) -> str:
        """Return the component name."""
        return self._name

    # Cargo-cult from components/proxy/camera.py
    def camera_image(self) -> Optional[bytes]:
        """Return camera image."""
        return run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop).result()

    def __needs_refresh(self) -> bool:
        if not (self._delta and self._deadline and self._last_image):
            return True

        return dt_util.utcnow() > self._deadline

    async def __retrieve_radar_image(self) -> bool:
        """Retrieve new radar image and return whether this succeeded."""
        session = async_get_clientsession(self._hass)

        url = RADAR_MAP_URL_TEMPLATE.format(w=self._dimension,
                                            h=self._dimension)

        if self._last_modified:
            headers = {'If-Modified-Since': self._last_modified}
        else:
            headers = {}

        try:
            async with session.get(url, timeout=5, headers=headers) as res:
                if res.status == 304:
                    _LOG.debug("HTTP 304 - success")
                    return True
                if res.status != 200:
                    _LOG.error("HTTP %s - failure", res.status)
                    return False

                last_modified = res.headers.get('Last-Modified', None)
                if last_modified:
                    self._last_modified = last_modified

                self._last_image = await res.read()
                _LOG.debug("HTTP 200 - Last-Modified: %s", last_modified)

                return True
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOG.error("Failed to fetch image, %s", type(err))
            return False

    async def async_camera_image(self) -> Optional[bytes]:
        """
        Return a still image response from the camera.

        Uses ayncio conditions to make sure only one task enters the critical
        section at the same time. Othertwise, two http requests would start
        when two tabs with home assistant are open.

        An additional boolean (_loading) is used to indicate the loading status
        instead of _last_image since that is initialized to None.
        """
        if not self.__needs_refresh():
            return self._last_image

        # get lock, check iff loading, await notification if loading
        async with self._condition:
            if self._loading:
                _LOG.debug("already loading - waiting for notification")
                await self._condition.wait()
                return self._last_image

            # Set loading status **while holding lock**, makes other tasks wait
            self._loading = True

        try:
            now = dt_util.utcnow()
            res = await self.__retrieve_radar_image()
            # successful response? update deadline to time before loading
            if res:
                self._deadline = now + timedelta(seconds=self._delta)

            return self._last_image
        finally:
            # get lock, unset loading status, notify all waiting tasks
            async with self._condition:
                self._loading = False
                self._condition.notify_all()
