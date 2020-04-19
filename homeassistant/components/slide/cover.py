"""Support for Slide slides."""

import logging

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_CURTAIN,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPENING,
    CoverDevice,
)
from homeassistant.const import ATTR_ID

from .const import API, DEFAULT_OFFSET, DOMAIN, SLIDES

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up cover(s) for Slide platform."""

    if discovery_info is None:
        return

    entities = []

    for slide in hass.data[DOMAIN][SLIDES].values():
        _LOGGER.debug("Setting up Slide entity: %s", slide)
        entities.append(SlideCover(hass.data[DOMAIN][API], slide))

    async_add_entities(entities)


class SlideCover(CoverDevice):
    """Representation of a Slide cover."""

    def __init__(self, api, slide):
        """Initialize the cover."""
        self._api = api
        self._slide = slide
        self._id = slide["id"]
        self._unique_id = slide["mac"]
        self._name = slide["name"]
        self._invert = slide["invert"]

    @property
    def unique_id(self):
        """Return the device unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {ATTR_ID: self._id}

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._slide["state"] == STATE_OPENING

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._slide["state"] == STATE_CLOSING

    @property
    def is_closed(self):
        """Return None if status is unknown, True if closed, else False."""
        if self._slide["state"] is None:
            return None
        return self._slide["state"] == STATE_CLOSED

    @property
    def available(self):
        """Return False if state is not available."""
        return self._slide["online"]

    @property
    def assumed_state(self):
        """Let HA know the integration is assumed state."""
        return True

    @property
    def device_class(self):
        """Return the device class of the cover."""
        return DEVICE_CLASS_CURTAIN

    @property
    def current_cover_position(self):
        """Return the current position of cover shutter."""
        pos = self._slide["pos"]
        if pos is not None:
            if (1 - pos) <= DEFAULT_OFFSET or pos <= DEFAULT_OFFSET:
                pos = round(pos)
            if not self._invert:
                pos = 1 - pos
            pos = int(pos * 100)
        return pos

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._slide["state"] = STATE_OPENING
        await self._api.slide_open(self._id)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._slide["state"] = STATE_CLOSING
        await self._api.slide_close(self._id)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._api.slide_stop(self._id)

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION] / 100
        if not self._invert:
            position = 1 - position

        if self._slide["pos"] is not None:
            if position > self._slide["pos"]:
                self._slide["state"] = STATE_CLOSING
            else:
                self._slide["state"] = STATE_OPENING

        await self._api.slide_set_position(self._id, position)
