"""Sandbox proxy for todo entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
from homeassistant.core import callback

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxTodoListEntity(SandboxProxyEntity, TodoListEntity):
    """Proxy for a todo list entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy todo entity."""
        super().__init__(description, manager)
        self._attr_supported_features = TodoListEntityFeature(
            description.supported_features
        )
        self._attr_todo_items: list[TodoItem] | None = None

    @callback
    def sandbox_update_state(self, state: str, attributes: dict[str, Any]) -> None:
        """Update todo items from sandbox push."""
        if "todo_items" in attributes:
            items = []
            for item_data in attributes["todo_items"]:
                items.append(TodoItem(
                    uid=item_data.get("uid"),
                    summary=item_data.get("summary", ""),
                    status=TodoItemStatus(item_data["status"]) if "status" in item_data else None,
                    description=item_data.get("description"),
                    due=item_data.get("due"),
                ))
            self._attr_todo_items = items
        self._state_cache["state"] = state
        self.async_write_ha_state()

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Return the todo items."""
        return self._attr_todo_items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Forward create_todo_item to sandbox."""
        await self._forward_method("async_create_todo_item", item={
            "summary": item.summary,
            "status": item.status.value if item.status else None,
            "description": item.description,
            "due": item.due,
        })

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Forward update_todo_item to sandbox."""
        await self._forward_method("async_update_todo_item", item={
            "uid": item.uid,
            "summary": item.summary,
            "status": item.status.value if item.status else None,
            "description": item.description,
            "due": item.due,
        })

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Forward delete_todo_items to sandbox."""
        await self._forward_method("async_delete_todo_items", uids=uids)
