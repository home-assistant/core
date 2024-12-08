"""Support for Slide covers."""

from __future__ import annotations

import logging
from typing import Any

from goslideapi.goslideapi import (
    ClientConnectionError,
    ClientTimeoutError,
    GoSlideLocal as SlideLocalApi,
)
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    PLATFORM_SCHEMA as COVER_PLATFORM_SCHEMA,
    CoverDeviceClass,
    CoverEntity,
)
from homeassistant.const import (
    ATTR_ID,
    CONF_API_VERSION,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_TOUCHGO,
    CONF_INVERT_POSITION,
    DEFAULT_OFFSET,
    SERVICE_CALIBRATE,
    SERVICE_TOUCHGO,
)
from .models import SlideConfigEntry

COVER_PLATFORM_SCHEMA = COVER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_INVERT_POSITION, default=False): cv.boolean,
        vol.Optional(CONF_API_VERSION, default=2): cv.byte,
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SlideConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cover(s) for Slide platform."""

    _LOGGER.debug("Initializing Slide cover(s)")

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CALIBRATE,
        None,
        "async_calibrate",
    )

    platform.async_register_entity_service(
        SERVICE_TOUCHGO,
        {vol.Required(ATTR_TOUCHGO): cv.boolean},
        "async_touchgo",
    )

    _LOGGER.debug(
        "Trying to setup Slide '%s', config=%s",
        entry.data[CONF_HOST],
        str(entry),
    )

    await entry.runtime_data.api.slide_add(
        entry.data[CONF_HOST],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_API_VERSION],
    )

    try:
        slide_info = await entry.runtime_data.api.slide_info(entry.runtime_data.host)
    except (ClientConnectionError, ClientTimeoutError) as err:
        # https://developers.home-assistant.io/docs/integration_setup_failures/

        _LOGGER.error(
            "Unable to get information from Slide '%s': %s",
            entry.runtime_data.host,
            str(err),
        )

    if slide_info is None:
        _LOGGER.error("Unable to setup Slide '%s'", entry.runtime_data.host)
    elif slide_info.get("mac") is None:
        _LOGGER.error(
            "Unable to setup Slide Local '%s', the MAC is missing in the slide response (%s)",
            entry.data[CONF_HOST],
            slide_info,
        )
    else:
        async_add_entities(
            [
                SlideCoverLocal(
                    entry.runtime_data.api,
                    slide_info,
                    entry.runtime_data.host,
                    entry.data[CONF_MAC],
                    entry.data[CONF_INVERT_POSITION],
                )
            ]
        )

        _LOGGER.debug("Setup Slide '%s' successful", entry.runtime_data.host)


class SlideCoverLocal(CoverEntity):
    """Representation of a Slide Local API cover."""

    _attr_assumed_state = True
    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_has_entity_name = True

    def __init__(
        self,
        api: SlideLocalApi,
        slide_info: dict[str, Any],
        host: str,
        mac: str,
        invert: bool,
    ) -> None:
        """Initialize the cover."""
        self._api = api
        self._id = host
        self._invert = invert
        self._name = slide_info.get("device_name", host)
        self._slide: dict[str, Any] = {}
        self._slide["pos"] = None
        self._slide["state"] = None
        self._slide["online"] = False
        self._slide["touchgo"] = False
        self._unique_id = mac

        self.parsedata(slide_info)

    @property
    def unique_id(self) -> str | None:
        """Return the device unique id."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
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
    def is_closed(self) -> bool:
        """Return None if status is unknown, True if closed, else False."""
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

        slide_info = None

        try:
            slide_info = await self._api.slide_info(self._id)
            self.parsedata(slide_info)
        except (ClientConnectionError, ClientTimeoutError) as err:
            # Set Slide to unavailable
            self._slide["online"] = False

            _LOGGER.error(
                "Unable to get information from Slide '%s': %s",
                self._id,
                str(err),
            )

    def parsedata(self, slide_info) -> None:
        """Parce data received from api."""

        self._slide["online"] = False

        if slide_info is None:
            _LOGGER.error("Slide '%s' returned no data (offline?)", self._id)
            return

        if "pos" in slide_info:
            oldpos = self._slide.get("pos")
            self._slide["online"] = True
            self._slide["touchgo"] = slide_info["touch_go"]
            self._slide["pos"] = slide_info["pos"]
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
            _LOGGER.error("Slide '%s' has invalid data %s", self._id, str(slide_info))

        # The format is:
        # {
        #   "slide_id": "slide_300000000000",
        #   "mac": "300000000000",
        #   "board_rev": 1,
        #   "device_name": "",
        #   "zone_name": "",
        #   "curtain_type": 0,
        #   "calib_time": 10239,
        #   "pos": 0.0,
        #   "touch_go": true
        # }

    async def async_calibrate(self) -> None:
        """Calibrate the Slide."""
        await self._api.slide_calibrate(self._id)

    async def async_touchgo(self, **kwargs) -> None:
        """TouchGo the Slide."""
        await self._api.slide_set_touchgo(self._id, kwargs[ATTR_TOUCHGO])
