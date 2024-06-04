"""Todo platform for the TickTick integration."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

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
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import TickTickDataUpdateCoordinator

SCAN_INTERVAL = timedelta(minutes=15)

TODO_STATUS_MAP = {
    "needsAction": TodoItemStatus.NEEDS_ACTION,
    "completed": TodoItemStatus.COMPLETED,
}
TODO_STATUS_MAP_INV = {v: k for k, v in TODO_STATUS_MAP.items()}


def _convert_todo_item(item: TodoItem) -> dict[str, Any]:
    """Convert TodoItem dataclass items to dictionary of attributes for the TickTick API."""
    result: dict[str, Any] = {
        "title": item.summary,
        "status": TODO_STATUS_MAP_INV.get(item.status, "needsAction"),
        "content": item.description,
    }
    if (due := item.due) is not None:
        result["dueDate"] = dt_util.start_of_local_day(due).isoformat()
    return result


def _convert_api_item(item: dict[str, Any]) -> TodoItem:
    """Convert TickTick API items into a TodoItem."""
    due: date | None = None
    if (due_str := item.get("dueDate")) is not None:
        due = datetime.fromisoformat(due_str).date()
    return TodoItem(
        summary=item["title"],
        uid=item["id"],
        status=TODO_STATUS_MAP.get(
            item.get("status", ""),
            TodoItemStatus.NEEDS_ACTION,
        ),
        due=due,
        description=item.get("content"),
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the TickTick todo platform."""
    cooridator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        TickTickTodoListEntity(
            cooridator, project["name"], entry.entry_id, project["id"]
        )
        for project in cooridator.ticktick_client.state["projects"]
    )


class TickTickTodoListEntity(
    CoordinatorEntity[TickTickDataUpdateCoordinator], TodoListEntity
):
    """A To-do List representation of the TickTick project."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(
        self,
        coordinator: TickTickDataUpdateCoordinator,
        project_name,
        config_entry_id,
        project_id,
    ) -> None:
        """Initialize TickTickTodoListEntity."""
        super().__init__(coordinator)
        self._attr_name = project_name.capitalize()
        self._attr_unique_id = f"{config_entry_id}-{project_id}"
        self._project_id = project_id

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Get the current set of To-do items."""
        if self.coordinator.data is None:
            return None
        return [
            _convert_api_item(item)
            for item in self.coordinator.ticktick_client.state["tasks"]
            if item["projectId"] == self._project_id
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        await self.hass.async_add_executor_job(
            self.coordinator.ticktick_client.task.create,
            _convert_todo_item(item),
        )
        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        await self.hass.async_add_executor_job(
            self.coordinator.ticktick_client.task.update,
            _convert_todo_item(item),
        )
        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete To-do items."""
        await self.hass.async_add_executor_job(
            self.coordinator.ticktick_client.task.delete,
            [{"id": uid} for uid in uids],
        )
        await self.coordinator.async_refresh()

    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Re-order a To-do item."""
        # Implement the move functionality if TickTick supports re-ordering tasks
