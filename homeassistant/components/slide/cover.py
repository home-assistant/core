"""Support for Slide slides."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import ATTR_POSITION, CoverDeviceClass, CoverEntity
from homeassistant.const import ATTR_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import API, DEFAULT_OFFSET, DOMAIN, SLIDES

_LOGGER = logging.getLogger(__name__)

CLOSED = "closed"
CLOSING = "closing"
OPENING = "opening"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up cover(s) for Slide platform."""

    if discovery_info is None:
        return

    entities = []

    for slide in hass.data[DOMAIN][SLIDES].values():
        _LOGGER.debug("Setting up Slide entity: %s", slide)
        entities.append(SlideCover(hass.data[DOMAIN][API], slide))

    async_add_entities(entities)


class SlideCover(CoverEntity):
    """Representation of a Slide cover."""

    _attr_assumed_state = True
    _attr_device_class = CoverDeviceClass.CURTAIN

    def __init__(self, api, slide):
        """Initialize the cover."""
        self._api = api
        self._slide = slide
        self._id = slide["id"]
        self._attr_extra_state_attributes = {ATTR_ID: self._id}
        self._attr_unique_id = slide["mac"]
        self._attr_name = slide["name"]
        self._invert = slide["invert"]

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._slide["state"] == OPENING

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._slide["state"] == CLOSING

    @property
    def is_closed(self) -> bool | None:
        """Return None if status is unknown, True if closed, else False."""
        if self._slide["state"] is None:
            return None
        return self._slide["state"] == CLOSED

    @property
    def available(self) -> bool:
        """Return False if state is not available."""
        return self._slide["online"]

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of cover shutter."""
        if (pos := self._slide["pos"]) is not None:
            if (1 - pos) <= DEFAULT_OFFSET or pos <= DEFAULT_OFFSET:
                pos = round(pos)
            if not self._invert:
                pos = 1 - pos
            pos = int(pos * 100)
        return pos

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._slide["state"] = OPENING
        await self._api.slide_open(self._id)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._slide["state"] = CLOSING
        await self._api.slide_close(self._id)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._api.slide_stop(self._id)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION] / 100
        if not self._invert:
            position = 1 - position

        if self._slide["pos"] is not None:
            if position > self._slide["pos"]:
                self._slide["state"] = CLOSING
            else:
                self._slide["state"] = OPENING

        await self._api.slide_set_position(self._id, position)
