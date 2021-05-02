"""Provide animated GIF loops of Buienradar imagery."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

import aiohttp

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_COUNTRY,
    CONF_DELTA,
    DEFAULT_COUNTRY,
    DEFAULT_DELTA,
    DEFAULT_DIMENSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up buienradar radar-loop camera component."""
    config = entry.data
    options = entry.options

    country = options.get(CONF_COUNTRY, config.get(CONF_COUNTRY, DEFAULT_COUNTRY))

    delta = options.get(CONF_DELTA, config.get(CONF_DELTA, DEFAULT_DELTA))

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    async_add_entities([BuienradarCam(latitude, longitude, delta, country)])


class BuienradarCam(Camera):
    """
    A camera component producing animated buienradar radar-imagery GIFs.

    Rain radar imagery camera based on image URL taken from [0].

    [0]: https://www.buienradar.nl/overbuienradar/gratis-weerdata
    """

    def __init__(
        self, latitude: float, longitude: float, delta: float, country: str
    ) -> None:
        """
        Initialize the component.

        This constructor must be run in the event loop.
        """
        super().__init__()

        self._name = "Buienradar"

        # dimension (x and y) of returned radar image
        self._dimension = DEFAULT_DIMENSION

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

        self._last_image: bytes | None = None
        # value of the last seen last modified header
        self._last_modified: str | None = None
        # loading status
        self._loading = False
        # deadline for image refresh - self.delta after last successful load
        self._deadline: datetime | None = None

        self._unique_id = f"{latitude:2.6f}{longitude:2.6f}"

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
                    _LOGGER.debug("HTTP 304 - success")
                    return True

                last_modified = res.headers.get("Last-Modified")
                if last_modified:
                    self._last_modified = last_modified

                self._last_image = await res.read()
                _LOGGER.debug("HTTP 200 - Last-Modified: %s", last_modified)

                return True
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Failed to fetch image, %s", type(err))
            return False

    async def async_camera_image(self) -> bytes | None:
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
                _LOGGER.debug("already loading - waiting for notification")
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

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Disable entity by default."""
        return False
