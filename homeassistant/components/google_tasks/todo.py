"""Google Tasks todo platform."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, cast

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import GoogleTasksConfigEntry, TaskUpdateCoordinator

PARALLEL_UPDATES = 0

TODO_STATUS_MAP = {
    "needsAction": TodoItemStatus.NEEDS_ACTION,
    "completed": TodoItemStatus.COMPLETED,
}
TODO_STATUS_MAP_INV = {v: k for k, v in TODO_STATUS_MAP.items()}


def _convert_todo_item(item: TodoItem) -> dict[str, str | None]:
    """Convert TodoItem dataclass items to dictionary of attributes the tasks API."""
    result: dict[str, str | None] = {}
    result["title"] = item.summary
    if item.status is not None:
        result["status"] = TODO_STATUS_MAP_INV[item.status]
    else:
        result["status"] = TodoItemStatus.NEEDS_ACTION
    if (due := item.due) is not None:
        # due API field is a timestamp string, but with only date resolution.
        # The time portion of the date is always discarded by the API, so we
        # always set to UTC.
        result["due"] = dt_util.start_of_local_day(due).replace(tzinfo=UTC).isoformat()
    else:
        result["due"] = None
    result["notes"] = item.description
    return result


def _convert_api_item(item: dict[str, str]) -> TodoItem:
    """Convert tasks API items into a TodoItem."""
    due: date | None = None
    if (due_str := item.get("due")) is not None:
        # Due dates are returned always in UTC so we only need to
        # parse the date portion which will be interpreted as a a local date.
        due = datetime.fromisoformat(due_str).date()
    return TodoItem(
        summary=item["title"],
        uid=item["id"],
        status=TODO_STATUS_MAP.get(
            item.get("status", ""),
            TodoItemStatus.NEEDS_ACTION,
        ),
        due=due,
        description=item.get("notes"),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleTasksConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Google Tasks todo platform."""
    async_add_entities(
        (
            GoogleTaskTodoListEntity(
                coordinator,
                coordinator.task_list_title,
                entry.entry_id,
                coordinator.task_list_id,
            )
            for coordinator in entry.runtime_data
        ),
    )


class GoogleTaskTodoListEntity(
    CoordinatorEntity[TaskUpdateCoordinator], TodoListEntity
):
    """A To-do List representation of the Shopping List."""

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
        coordinator: TaskUpdateCoordinator,
        name: str,
        config_entry_id: str,
        task_list_id: str,
    ) -> None:
        """Initialize GoogleTaskTodoListEntity."""
        super().__init__(coordinator)
        self._attr_name = name.capitalize()
        self._attr_unique_id = f"{config_entry_id}-{task_list_id}"
        self._task_list_id = task_list_id

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Get the current set of To-do items."""
        return [_convert_api_item(item) for item in _order_tasks(self.coordinator.data)]

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

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete To-do items."""
        await self.coordinator.api.delete(self._task_list_id, uids)
        await self.coordinator.async_refresh()

    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Re-order a To-do item."""
        await self.coordinator.api.move(self._task_list_id, uid, previous=previous_uid)
        await self.coordinator.async_refresh()


def _order_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order the task items response.

    All tasks have an order amongst their siblings based on position.

    Home Assistant To-do items do not support the Google Task parent/sibling
    relationships and the desired behavior is for them to be filtered.
    """
    parents = [task for task in tasks if task.get("parent") is None]
    parents.sort(key=lambda task: task["position"])
    return parents
