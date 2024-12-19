"""Support for Slide covers."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import ATTR_POSITION, CoverDeviceClass, CoverEntity
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPENING
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SlideConfigEntry
from .const import CONF_INVERT_POSITION, DEFAULT_OFFSET
from .coordinator import SlideCoordinator
from .entity import SlideEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SlideConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cover(s) for Slide platform."""

    coordinator = entry.runtime_data

    async_add_entities(
        [
            SlideCoverLocal(
                coordinator,
                entry,
            )
        ]
    )


class SlideCoverLocal(SlideEntity, CoverEntity):
    """Representation of a Slide Local API cover."""

    _attr_assumed_state = True
    _attr_device_class = CoverDeviceClass.CURTAIN

    def __init__(
        self,
        coordinator: SlideCoordinator,
        entry: SlideConfigEntry,
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator)

        self._attr_name = None
        self.invert = entry.options[CONF_INVERT_POSITION]
        self._attr_unique_id = coordinator.data["mac"]

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self.coordinator.data["state"] == STATE_OPENING

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self.coordinator.data["state"] == STATE_CLOSING

    @property
    def is_closed(self) -> bool:
        """Return None if status is unknown, True if closed, else False."""
        return self.coordinator.data["state"] == STATE_CLOSED

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of cover shutter."""
        pos = self.coordinator.data["pos"]
        if pos is not None:
            if (1 - pos) <= DEFAULT_OFFSET or pos <= DEFAULT_OFFSET:
                pos = round(pos)
            if not self.invert:
                pos = 1 - pos
            pos = int(pos * 100)
        return pos

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self.coordinator.data["state"] = STATE_OPENING
        await self.coordinator.slide.slide_open(self.coordinator.host)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self.coordinator.data["state"] = STATE_CLOSING
        await self.coordinator.slide.slide_close(self.coordinator.host)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.coordinator.slide.slide_stop(self.coordinator.host)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION] / 100
        if not self.invert:
            position = 1 - position

        if self.coordinator.data["pos"] is not None:
            if position > self.coordinator.data["pos"]:
                self.coordinator.data["state"] = STATE_CLOSING
            else:
                self.coordinator.data["state"] = STATE_OPENING

        await self.coordinator.slide.slide_set_position(self.coordinator.host, position)
