"""Support for control of ElkM1 tasks ("macros")."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.scene import Scene

from . import ElkAttachedEntity, ElkEntity, ElkM1ConfigEntry, create_elk_entities

if TYPE_CHECKING:
    from elkm1_lib.tasks import Task

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ElkM1ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the Elk-M1 scene platform."""
    elk_data = config_entry.runtime_data
    elk = elk_data.elk
    entities: list[ElkEntity] = []
    create_elk_entities(elk_data, elk.tasks, "task", ElkTask, entities)
    async_add_entities(entities)


class ElkTask(ElkAttachedEntity, Scene):
    """Elk-M1 task as scene."""

    _element: Task

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the task."""
        self._element.activate()
