"""Support for Slide covers."""

from __future__ import annotations

import logging
from typing import Any

from goslideapi import GoSlideLocal
import voluptuous as vol

from homeassistant.components.cover import ATTR_POSITION, CoverDeviceClass, CoverEntity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ID,
    CONF_HOST,
    CONF_PASSWORD,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    API,
    ATTR_TOUCHGO,
    CONF_API_VERSION,
    CONF_INVERT_POSITION,
    DEFAULT_OFFSET,
    DOMAIN,
    SERVICE_CALIBRATE,
)

SERVICE_SCHEMA_CALIBRATE = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up cover(s) for Slide platform."""

    _LOGGER.debug("Initializing Slide cover(s)")

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CALIBRATE,
        SERVICE_SCHEMA_CALIBRATE,
        "async_calibrate",
    )

    if API not in hass.data[DOMAIN]:
        hass.data[DOMAIN][API] = GoSlideLocal()

    if discovery_info:
        cover = discovery_info
        _LOGGER.debug(
            "Trying to setup Slide '%s', config=%s",
            cover[CONF_HOST],
            str(cover),
        )

        await hass.data[DOMAIN][API].slide_add(
            cover[CONF_HOST], cover[CONF_PASSWORD], cover[CONF_API_VERSION]
        )

        slide_info = await hass.data[DOMAIN][API].slide_info(cover[CONF_HOST])

        if slide_info is not None:
            _LOGGER.debug("Setup Slide '%s' successful", cover[CONF_HOST])

            async_add_entities(
                [
                    SlideCover(
                        hass.data[DOMAIN][API],
                        slide_info,
                        cover[CONF_HOST],
                        cover[CONF_INVERT_POSITION],
                    )
                ]
            )
        else:
            _LOGGER.error("Unable to setup Slide '%s'", cover[CONF_HOST])

        return

    if not config:
        _LOGGER.error("Something wrong in 'cover:' section?")
        return


class SlideCover(CoverEntity):
    """Representation of a Slide Local API cover."""

    _attr_assumed_state = True
    _attr_device_class = CoverDeviceClass.CURTAIN

    def __init__(
        self, api: GoSlideLocal, slide_info: dict[str, Any], host: str, invert: bool
    ) -> None:
        """Initialize the cover."""
        self._api = api
        self._slide: dict[str, Any] = {}
        self._slide["pos"] = None
        self._slide["state"] = None
        self._slide["online"] = False
        self._slide["touchgo"] = False
        self._unique_id: str | None = None

        self.parsedata(slide_info)

        self._id = host
        self._invert = invert
        self._name = host
        if self._unique_id is None:
            _LOGGER.error(
                "Unable to setup Slide Local '%s', the MAC is missing in the Slide response",
                self._id,
            )
            return

    @property
    def unique_id(self) -> str | None:
        """Return the device unique id."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {ATTR_ID: self._id, ATTR_TOUCHGO: self._slide["touchgo"]}

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._slide["state"] == STATE_OPENING

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._slide["state"] == STATE_CLOSING

    @property
    def is_closed(self) -> bool | None:
        """Return None if status is unknown, True if closed, else False."""
        if self._slide["state"] is None:
            return None
        return self._slide["state"] == STATE_CLOSED

    @property
    def available(self) -> bool:
        """Return False if state is not available."""
        return self._slide["online"]

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of cover shutter."""
        pos = self._slide["pos"]
        if pos is not None:
            if (1 - pos) <= DEFAULT_OFFSET or pos <= DEFAULT_OFFSET:
                pos = round(pos)
            if not self._invert:
                pos = 1 - pos
            pos = int(pos * 100)
        return pos

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._slide["state"] = STATE_OPENING
        await self._api.slide_open(self._id)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._slide["state"] = STATE_CLOSING
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
                self._slide["state"] = STATE_CLOSING
            else:
                self._slide["state"] = STATE_OPENING

        await self._api.slide_set_position(self._id, position)

    async def async_update(self) -> None:
        """Update slide information."""

        slide = await self._api.slide_info(self._id)
        self.parsedata(slide)

    def parsedata(self, slide) -> None:
        """Parse slide information."""

        self._slide["online"] = False

        if slide is None:
            _LOGGER.error("Slide '%s' returned no data (offline?)", self._id)
            return

        if "pos" in slide:
            if self._unique_id is None:
                self._unique_id = slide["slide_id"]
            oldpos = self._slide.get("pos")
            self._slide["online"] = True
            self._slide["touchgo"] = slide["touch_go"]
            self._slide["pos"] = slide["pos"]
            self._slide["pos"] = max(0, min(1, self._slide["pos"]))

            if oldpos is None or oldpos == self._slide["pos"]:
                self._slide["state"] = (
                    STATE_CLOSED
                    if self._slide["pos"] > (1 - DEFAULT_OFFSET)
                    else STATE_OPEN
                )
            elif oldpos < self._slide["pos"]:
                self._slide["state"] = (
                    STATE_CLOSED
                    if self._slide["pos"] >= (1 - DEFAULT_OFFSET)
                    else STATE_CLOSING
                )
            else:
                self._slide["state"] = (
                    STATE_OPEN
                    if self._slide["pos"] <= DEFAULT_OFFSET
                    else STATE_OPENING
                )
        else:
            _LOGGER.error("Slide '%s' has invalid data %s", self._id, str(slide))

    async def async_calibrate(self) -> None:
        """Calibrate the Slide."""
        await self._api.slide_calibrate(self._id)
