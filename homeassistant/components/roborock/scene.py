"""Support for Roborock scene."""

from __future__ import annotations

import asyncio
from typing import Any

from roborock.containers import HomeDataScene

from homeassistant.components.scene import Scene as SceneEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RoborockConfigEntry
from .coordinator import RoborockDataUpdateCoordinator
from .entity import RoborockEntity


async def _setup_coordinator(
    coordinator: RoborockDataUpdateCoordinator,
) -> list[SceneEntity]:
    return [
        RoborockSceneEntity(coordinator, scene)
        for scene in await coordinator.get_scenes()
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scene platform."""
    coordinator_entities = await asyncio.gather(
        *[
            _setup_coordinator(coordinator)
            for coordinator in config_entry.runtime_data.v1
        ],
        return_exceptions=True,
    )
    async_add_entities(
        entity
        for entities in coordinator_entities
        if isinstance(entities, list)
        for entity in entities
    )


class RoborockSceneEntity(RoborockEntity, SceneEntity):
    """A class to define Roborock scene entities."""

    entity_description: EntityDescription

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinator,
        scene: HomeDataScene,
    ) -> None:
        """Create a scene entity."""
        super().__init__(
            f"{scene.id}_{coordinator.duid_slug}",
            coordinator.device_info,
            coordinator.api,
        )
        self._scene_id = scene.id
        self._coordinator = coordinator
        self.entity_description = EntityDescription(
            key=str(scene.id),
            name=scene.name,
        )

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._coordinator.execute_scene(self._scene_id)
