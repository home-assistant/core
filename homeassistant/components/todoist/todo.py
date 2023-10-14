"""A todo platform for Todoist."""

import asyncio
import logging
from typing import cast

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

from .const import DOMAIN
from .coordinator import TodoistCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Todoist todo platform config entry."""
    coordinator: TodoistCoordinator = hass.data[DOMAIN][entry.entry_id]
    projects = await coordinator.async_get_projects()
    async_add_entities(
        TodoistTodoListEntity(coordinator, entry.unique_id, project.id, project.name)
        for project in projects
    )


class TodoistTodoListEntity(CoordinatorEntity[TodoistCoordinator], TodoListEntity):
    """A Todoist TodoListEntity."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(
        self,
        coordinator: TodoistCoordinator,
        config_entry_unique_id: str | None,
        project_id: str,
        project_name: str,
    ) -> None:
        """Initialize TodoistTodoListEntity."""
        super().__init__(coordinator=coordinator)
        self._project_id = project_id
        if config_entry_unique_id:
            self._attr_unique_id = f"{config_entry_unique_id}-{project_id}"
        self._attr_name = project_name

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is None:
            self._attr_todo_items = None
        else:
            items = []
            for task in self.coordinator.data:
                if task.is_completed:
                    status = TodoItemStatus.COMPLETED
                else:
                    status = TodoItemStatus.NEEDS_ACTION
                items.append(
                    TodoItem(
                        summary=task.content,
                        uid=task.id,
                        status=status,
                    )
                )
            self._attr_todo_items = items
        super()._handle_coordinator_update()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a To-do item."""
        if item.status != TodoItemStatus.NEEDS_ACTION:
            raise ValueError("Only active tasks may be created.")
        logging.info("1 async_create_todo_item=%s", self._attr_todo_items)
        await self.coordinator.api.add_task(
            content=item.summary or "",
            project_id=self._project_id,
        )
        logging.info("2 async_create_todo_item=%s", self._attr_todo_items)
        await self.coordinator.async_refresh()
        logging.info("3 async_create_todo_item=%s", self._attr_todo_items)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        uid: str = cast(str, item.uid)
        if item.summary:
            await self.coordinator.api.update_task(task_id=uid, content=item.summary)
        if item.status is not None:
            if item.status == TodoItemStatus.COMPLETED:
                await self.coordinator.api.close_task(task_id=uid)
            else:
                await self.coordinator.api.reopen_task(task_id=uid)
        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete a To-do item."""
        tasks = []
        for uid in uids:
            tasks.append(self.coordinator.api.delete_task(task_id=uid))
        await asyncio.gather(*tasks)
        await self.coordinator.async_refresh()
