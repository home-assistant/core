"""Scene Platform for Niko Home Control."""

from __future__ import annotations

from typing import Any

from homeassistant.components.scene import BaseScene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NikoHomeControlConfigEntry
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

    _attr_name = None

    async def _async_activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        await self._action.activate()

    def update_state(self) -> None:
        """Update HA state."""
        self._async_record_activation()
