"""Support for Velbus covers."""
from __future__ import annotations

from typing import Any

from velbusaio.channels import Blind as VelbusBlind

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import VelbusEntity, api_call


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities = []
    for channel in cntrl.get_all("cover"):
        entities.append(VelbusCover(channel))
    async_add_entities(entities)


class VelbusCover(VelbusEntity, CoverEntity):
    """Representation a Velbus cover."""

    _channel: VelbusBlind

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

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self._channel.is_closed()

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return self._channel.is_opening()

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return self._channel.is_closing()

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
