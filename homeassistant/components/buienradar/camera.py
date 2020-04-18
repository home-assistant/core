"""Provide animated GIF loops of Buienradar imagery."""
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Optional

import aiohttp
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

CONF_DIMENSION = "dimension"
CONF_DELTA = "delta"
CONF_COUNTRY = "country_code"

_LOG = logging.getLogger(__name__)

# Maximum range according to docs
DIM_RANGE = vol.All(vol.Coerce(int), vol.Range(min=120, max=700))

# Multiple choice for available Radar Map URL
SUPPORTED_COUNTRY_CODES = ["NL", "BE"]

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_DIMENSION, default=512): DIM_RANGE,
            vol.Optional(CONF_DELTA, default=600.0): vol.All(
                vol.Coerce(float), vol.Range(min=0)
            ),
            vol.Optional(CONF_NAME, default="Buienradar loop"): cv.string,
            vol.Optional(CONF_COUNTRY, default="NL"): vol.All(
                vol.Coerce(str), vol.In(SUPPORTED_COUNTRY_CODES)
            ),
        }
    )
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up buienradar radar-loop camera component."""
    dimension = config[CONF_DIMENSION]
    delta = config[CONF_DELTA]
    name = config[CONF_NAME]
    country = config[CONF_COUNTRY]

    async_add_entities([BuienradarCam(name, dimension, delta, country)])


class BuienradarCam(Camera):
    """
    A camera component producing animated buienradar radar-imagery GIFs.

    Rain radar imagery camera based on image URL taken from [0].

    [0]: https://www.buienradar.nl/overbuienradar/gratis-weerdata
    """

    def __init__(self, name: str, dimension: int, delta: float, country: str):
        """
        Initialize the component.

        This constructor must be run in the event loop.
        """
        super().__init__()

        self._name = name

        # dimension (x and y) of returned radar image
        self._dimension = dimension

        # time a cached image stays valid for
        self._delta = delta

        # country location
        self._country = country

        # Condition that guards the loading indicator.
        #
        # Ensures that only one reader can cause an http request at the same
        # time, and that all readers are notified after this request completes.
        #
        # invariant: this condition is private to and owned by this instance.
        self._condition = asyncio.Condition()

        self._last_image: Optional[bytes] = None
        # value of the last seen last modified header
        self._last_modified: Optional[str] = None
        # loading status
        self._loading = False
        # deadline for image refresh - self.delta after last successful load
        self._deadline: Optional[datetime] = None

    @property
    def name(self) -> str:
        """Return the component name."""
        return self._name

    def __needs_refresh(self) -> bool:
        if not (self._delta and self._deadline and self._last_image):
            return True

        return dt_util.utcnow() > self._deadline

    async def __retrieve_radar_image(self) -> bool:
        """Retrieve new radar image and return whether this succeeded."""
        session = async_get_clientsession(self.hass)

        url = (
            f"https://api.buienradar.nl/image/1.0/RadarMap{self._country}"
            f"?w={self._dimension}&h={self._dimension}"
        )

        if self._last_modified:
            headers = {"If-Modified-Since": self._last_modified}
        else:
            headers = {}

        try:
            async with session.get(url, timeout=5, headers=headers) as res:
                res.raise_for_status()

                if res.status == 304:
                    _LOG.debug("HTTP 304 - success")
                    return True

                last_modified = res.headers.get("Last-Modified")
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
        section at the same time. Otherwise, two http requests would start
        when two tabs with Home Assistant are open.

        The condition is entered in two sections because otherwise the lock
        would be held while doing the http request.

        A boolean (_loading) is used to indicate the loading status instead of
        _last_image since that is initialized to None.

        For reference:
          * :func:`asyncio.Condition.wait` releases the lock and acquires it
            again before continuing.
          * :func:`asyncio.Condition.notify_all` requires the lock to be held.
        """
        if not self.__needs_refresh():
            return self._last_image

        # get lock, check iff loading, await notification if loading
        async with self._condition:
            # can not be tested - mocked http response returns immediately
            if self._loading:
                _LOG.debug("already loading - waiting for notification")
                await self._condition.wait()
                return self._last_image

            # Set loading status **while holding lock**, makes other tasks wait
            self._loading = True

        try:
            now = dt_util.utcnow()
            was_updated = await self.__retrieve_radar_image()
            # was updated? Set new deadline relative to now before loading
            if was_updated:
                self._deadline = now + timedelta(seconds=self._delta)

            return self._last_image
        finally:
            # get lock, unset loading status, notify all waiting tasks
            async with self._condition:
                self._loading = False
                self._condition.notify_all()
