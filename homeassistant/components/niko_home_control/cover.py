"""Cover Platform for Niko Home Control."""

from __future__ import annotations

from typing import Any

from nhc.cover import NHCCover

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NikoHomeControlConfigEntry
from .entity import NikoHomeControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NikoHomeControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Niko Home Control cover entry."""
    controller = entry.runtime_data

    async_add_entities(
        NikoHomeControlCover(cover, controller, entry.entry_id)
        for cover in controller.covers
    )


class NikoHomeControlCover(NikoHomeControlEntity, CoverEntity):
    """Representation of a Niko Cover."""

    _attr_name = None
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _action: NHCCover

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._action.open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._action.close()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._action.stop()

    def update_state(self):
        """Update HA state."""
        self._attr_is_closed = self._action.state == 0
