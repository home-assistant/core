"""Support for VELUX scenes."""

from __future__ import annotations

from typing import Any

from pyvlx import Scene as PyVLXScene

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VeluxConfigEntry
from .const import DOMAIN

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the scenes for Velux platform."""
    pyvlx = config_entry.runtime_data
    async_add_entities(
        [VeluxScene(config_entry.entry_id, scene) for scene in pyvlx.scenes]
    )


class VeluxScene(Scene):
    """Representation of a Velux scene."""

    _attr_has_entity_name = True

    # Note: there's currently no code to update the scenes dynamically if changed in
    # the gateway. They're only loaded on integration setup (they're probably not
    # used heavily anyway since it's a pain to set them up in the gateway and so
    # much easier to use HA scenes).

    def __init__(self, config_entry_id: str, scene: PyVLXScene) -> None:
        """Init velux scene."""
        self.scene = scene
        # Renaming scenes in gateway keeps scene_id stable, we can use it as unique_id
        self._attr_unique_id = f"{config_entry_id}_scene_{scene.scene_id}"
        self._attr_name = scene.name

        # Associate scenes with the gateway device (where they are stored)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"gateway_{config_entry_id}")},
        )

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self.scene.run(wait_for_completion=False)
