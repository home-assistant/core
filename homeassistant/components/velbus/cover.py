"""Support for Velbus covers."""

from __future__ import annotations

from typing import Any

from velbusaio.channels import Blind as VelbusBlind

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity, api_call

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await entry.runtime_data.scan_task
    async_add_entities(
        VelbusCover(channel)
        for channel in entry.runtime_data.controller.get_all_cover()
    )


class VelbusCover(VelbusEntity, CoverEntity):
    """Representation a Velbus cover."""

    _channel: VelbusBlind
    _assumed_closed: bool

    def __init__(self, channel: VelbusBlind) -> None:
        """Initialize the cover."""
        super().__init__(channel)
        if self._channel.support_position():
            self._attr_supported_features = (
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.STOP
                | CoverEntityFeature.SET_POSITION
            )
        else:
            self._attr_supported_features = (
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.STOP
            )
            self._attr_assumed_state = True
            # guess the state to get the open/closed icons somewhat working
            self._assumed_closed = False

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._channel.support_position():
            return self._channel.is_closed()
        return self._assumed_closed

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        if opening := self._channel.is_opening():
            self._assumed_closed = False
        return opening

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        if closing := self._channel.is_closing():
            self._assumed_closed = True
        return closing

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open
        Velbus: 100 = closed, 0 = open
        """
        pos = self._channel.get_position()
        if pos is not None:
            return 100 - pos
        return None

    @api_call
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._channel.open()

    @api_call
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._channel.close()

    @api_call
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._channel.stop()

    @api_call
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self._channel.set_position(100 - kwargs[ATTR_POSITION])
