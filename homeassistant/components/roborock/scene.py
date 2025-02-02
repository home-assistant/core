"""Support for Roborock scene."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from roborock.containers import HomeDataScene

from homeassistant.components.scene import Scene as SceneEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RoborockConfigEntry
from .coordinator import RoborockDataUpdateCoordinator, RoborockDataUpdateCoordinatorA01
from .entity import RoborockEntity


async def _setup_coordinator(
    coordinator: RoborockDataUpdateCoordinator | RoborockDataUpdateCoordinatorA01,
) -> list[SceneEntity]:
    scenes = await coordinator.rest_api.get_scenes()
    return [RoborockSceneEntity(coordinator, scene) for scene in scenes]


def _build_setup_functions(
    coordinators: list[
        RoborockDataUpdateCoordinator | RoborockDataUpdateCoordinatorA01
    ],
) -> list[
    Coroutine[
        Any,
        Any,
        list[SceneEntity],
    ]
]:
    """Create a list of setup functions that can later be called asynchronously."""
    return [_setup_coordinator(coordinator) for coordinator in coordinators]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scene platform."""
    coordinator_entities = await asyncio.gather(
        *_build_setup_functions(config_entry.runtime_data.values()),
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
        coordinator: RoborockDataUpdateCoordinator | RoborockDataUpdateCoordinatorA01,
        scene: HomeDataScene,
    ) -> None:
        """Create a scene entity."""
        super().__init__(
            f"{scene.name}_{coordinator.duid_slug}",
            coordinator.device_info,
            coordinator.api,
        )
        self._scene_id = scene.id
        self._rest_api = coordinator.rest_api
        self.entity_description = EntityDescription(
            key=scene.name,
            name=scene.name,
        )

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._rest_api.execute_scene(self._scene_id)
