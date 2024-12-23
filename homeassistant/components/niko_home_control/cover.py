"""Cover Platform for Niko Home Control."""

from __future__ import annotations

from typing import Any

from nhc.cover import NHCCover

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NikoHomeControlConfigEntry
from .entity import NikoHomeControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NikoHomeControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
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

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._action.open()

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._action.close()

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._action.stop()

    def update_state(self):
        """Update HA state."""
        self._attr_is_closed = self._action.state == 0
