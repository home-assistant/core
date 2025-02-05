"""Support for Roborock scene."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.scene import Scene as SceneEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RoborockConfigEntry
from .coordinator import RoborockDataUpdateCoordinator
from .entity import RoborockEntity


async def _get_device_scenes(
    coordinator: RoborockDataUpdateCoordinator,
) -> list[SceneEntity]:
    return [
        RoborockSceneEntity(
            coordinator,
            EntityDescription(
                key=str(scene.id),
                name=scene.name,
            ),
        )
        for scene in await coordinator.get_scenes()
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scene platform."""
    devices_scene_entities = await asyncio.gather(
        *[
            _get_device_scenes(coordinator)
            for coordinator in config_entry.runtime_data.v1
        ],
    )
    async_add_entities(
        entity
        for device_scene_entities in devices_scene_entities
        for entity in device_scene_entities
    )


class RoborockSceneEntity(RoborockEntity, SceneEntity):
    """A class to define Roborock scene entities."""

    entity_description: EntityDescription

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Create a scene entity."""
        super().__init__(
            f"{entity_description.key}_{coordinator.duid_slug}",
            coordinator.device_info,
            coordinator.api,
        )
        self._scene_id = int(entity_description.key)
        self._coordinator = coordinator
        self.entity_description = entity_description

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._coordinator.execute_scene(self._scene_id)
