"""Google Tasks todo platform."""
from __future__ import annotations

from datetime import timedelta
from typing import cast

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AsyncConfigEntryAuth
from .const import DOMAIN
from .coordinator import TaskUpdateCoordinator

SCAN_INTERVAL = timedelta(minutes=15)

TODO_STATUS_MAP = {
    "needsAction": TodoItemStatus.NEEDS_ACTION,
    "completed": TodoItemStatus.COMPLETED,
}
TODO_STATUS_MAP_INV = {v: k for k, v in TODO_STATUS_MAP.items()}


def _convert_todo_item(item: TodoItem) -> dict[str, str]:
    """Convert TodoItem dataclass items to dictionary of attributes the tasks API."""
    result: dict[str, str] = {}
    if item.summary is not None:
        result["title"] = item.summary
    if item.status is not None:
        result["status"] = TODO_STATUS_MAP_INV[item.status]
    return result


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Google Tasks todo platform."""
    api: AsyncConfigEntryAuth = hass.data[DOMAIN][entry.entry_id]
    task_lists = await api.list_task_lists()
    async_add_entities(
        (
            GoogleTaskTodoListEntity(
                TaskUpdateCoordinator(hass, api, task_list["id"]),
                task_list["title"],
                entry.entry_id,
                task_list["id"],
            )
            for task_list in task_lists
        ),
        True,
    )


class GoogleTaskTodoListEntity(
    CoordinatorEntity[TaskUpdateCoordinator], TodoListEntity
):
    """A To-do List representation of the Shopping List."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM | TodoListEntityFeature.UPDATE_TODO_ITEM
    )

    def __init__(
        self,
        coordinator: TaskUpdateCoordinator,
        name: str,
        config_entry_id: str,
        task_list_id: str,
    ) -> None:
        """Initialize LocalTodoListEntity."""
        super().__init__(coordinator)
        self._attr_name = name.capitalize()
        self._attr_unique_id = f"{config_entry_id}-{task_list_id}"
        self._task_list_id = task_list_id

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Get the current set of To-do items."""
        if self.coordinator.data is None:
            return None
        return [
            TodoItem(
                summary=item["title"],
                uid=item["id"],
                status=TODO_STATUS_MAP.get(
                    item.get("status"), TodoItemStatus.NEEDS_ACTION  # type: ignore[arg-type]
                ),
            )
            for item in self.coordinator.data
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        await self.coordinator.api.insert(
            self._task_list_id,
            task=_convert_todo_item(item),
        )
        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        uid: str = cast(str, item.uid)
        await self.coordinator.api.patch(
            self._task_list_id,
            uid,
            task=_convert_todo_item(item),
        )
        await self.coordinator.async_refresh()
