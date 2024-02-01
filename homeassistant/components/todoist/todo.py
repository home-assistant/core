"""A todo platform for Todoist."""

import asyncio
import datetime
from typing import Any, cast

from todoist_api_python.models import Task

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import TodoistCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Todoist todo platform config entry."""
    coordinator: TodoistCoordinator = hass.data[DOMAIN][entry.entry_id]
    projects = await coordinator.async_get_projects()
    async_add_entities(
        TodoistTodoListEntity(coordinator, entry.entry_id, project.id, project.name)
        for project in projects
    )


def _task_api_data(item: TodoItem, api_data: Task | None = None) -> dict[str, Any]:
    """Convert a TodoItem to the set of add or update arguments."""
    item_data: dict[str, Any] = {
        "content": item.summary,
        # Description needs to be empty string to be cleared
        "description": item.description or "",
    }
    if due := item.due:
        if isinstance(due, datetime.datetime):
            item_data["due_datetime"] = due.isoformat()
        else:
            item_data["due_date"] = due.isoformat()
        # In order to not lose any recurrence metadata for the task, we need to
        # ensure that we send the `due_string` param if the task has it set.
        # NOTE: It's ok to send stale data for non-recurring tasks. Any provided
        # date/datetime will override this string.
        if api_data and api_data.due:
            item_data["due_string"] = api_data.due.string
    else:
        # Special flag "no date" clears the due date/datetime.
        # See https://developer.todoist.com/rest/v2/#update-a-task for more.
        item_data["due_string"] = "no date"
    return item_data


class TodoistTodoListEntity(CoordinatorEntity[TodoistCoordinator], TodoListEntity):
    """A Todoist TodoListEntity."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(
        self,
        coordinator: TodoistCoordinator,
        config_entry_id: str,
        project_id: str,
        project_name: str,
    ) -> None:
        """Initialize TodoistTodoListEntity."""
        super().__init__(coordinator=coordinator)
        self._project_id = project_id
        self._attr_unique_id = f"{config_entry_id}-{project_id}"
        self._attr_name = project_name

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is None:
            self._attr_todo_items = None
        else:
            items = []
            for task in self.coordinator.data:
                if task.project_id != self._project_id:
                    continue
                if task.parent_id is not None:
                    # Filter out sub-tasks until they are supported by the UI.
                    continue
                if task.is_completed:
                    status = TodoItemStatus.COMPLETED
                else:
                    status = TodoItemStatus.NEEDS_ACTION
                due: datetime.date | datetime.datetime | None = None
                if task_due := task.due:
                    if task_due.datetime:
                        due = dt_util.as_local(
                            datetime.datetime.fromisoformat(task_due.datetime)
                        )
                    elif task_due.date:
                        due = datetime.date.fromisoformat(task_due.date)
                items.append(
                    TodoItem(
                        summary=task.content,
                        uid=task.id,
                        status=status,
                        due=due,
                        description=task.description or None,  # Don't use empty string
                    )
                )
            self._attr_todo_items = items
        super()._handle_coordinator_update()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a To-do item."""
        if item.status != TodoItemStatus.NEEDS_ACTION:
            raise ValueError("Only active tasks may be created.")
        await self.coordinator.api.add_task(
            **_task_api_data(item),
            project_id=self._project_id,
        )
        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        uid: str = cast(str, item.uid)
        api_data = next((d for d in self.coordinator.data if d.id == uid), None)
        if update_data := _task_api_data(item, api_data):
            await self.coordinator.api.update_task(task_id=uid, **update_data)
        if item.status is not None:
            # Only update status if changed
            for existing_item in self._attr_todo_items or ():
                if existing_item.uid != item.uid:
                    continue

                if item.status != existing_item.status:
                    if item.status == TodoItemStatus.COMPLETED:
                        await self.coordinator.api.close_task(task_id=uid)
                    else:
                        await self.coordinator.api.reopen_task(task_id=uid)
        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete a To-do item."""
        await asyncio.gather(
            *[self.coordinator.api.delete_task(task_id=uid) for uid in uids]
        )
        await self.coordinator.async_refresh()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass update state from existing coordinator data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
