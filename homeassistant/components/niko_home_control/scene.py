"""Scene Platform for Niko Home Control."""

from __future__ import annotations

from typing import Any

from nhc.scene import NHCScene

from homeassistant.components.scene import BaseScene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import NHCController, NikoHomeControlConfigEntry
from .entity import NikoHomeControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NikoHomeControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Niko Home Control scene entry."""
    controller = entry.runtime_data

    async_add_entities(
        NikoHomeControlScene(scene, controller, entry.entry_id)
        for scene in controller.scenes
    )


class NikoHomeControlScene(NikoHomeControlEntity, BaseScene):
    """Representation of a Niko Home Control Scene."""

    def __init__(
        self, action: NHCScene, controller: NHCController, unique_id: str
    ) -> None:
        """Set up the Niko Home Control scene platform."""
        super().__init__(action, controller, unique_id)
        self._attr_icon = "mdi:palette"
        self._last_activated: str | None = None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "last_activated": self._last_activated,
        }

    async def _async_activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        await self._action.activate()

    def update_state(self) -> None:
        """Update HA state."""
        self._last_activated = dt_util.now().isoformat()
