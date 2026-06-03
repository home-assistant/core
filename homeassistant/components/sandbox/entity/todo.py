"""Sandbox v2 proxy for ``todo`` entities."""

from typing import TYPE_CHECKING

from homeassistant.components.todo import (
    TodoItem,
    TodoListEntity,
    TodoListEntityFeature,
)

from . import SandboxProxyEntity

if TYPE_CHECKING:
    from ..bridge import SandboxBridge, SandboxEntityDescription


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxTodoListEntity(SandboxProxyEntity, TodoListEntity):
    """Proxy for a ``todo`` (To-do list) entity in a sandbox."""

    def __init__(
        self,
        bridge: SandboxBridge,
        description: SandboxEntityDescription,
    ) -> None:
        """Wrap ``supported_features`` as ``TodoListEntityFeature``."""
        super().__init__(bridge, description)
        self._attr_supported_features = TodoListEntityFeature(
            description.supported_features or 0
        )

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Item iteration happens on the sandbox side; do not proxy items."""
        # The Phase-13 proxy only mirrors state + service calls. Listing
        # items is a server-side query that needs the same bridge plumbing
        # ``calendar`` does and is deferred until those operations get a
        # cross-process protocol (out of scope for this phase).
        return None

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Forward create as ``todo.add_item``."""
        await self._call_service("add_item", item=item.summary)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Forward update as ``todo.update_item``."""
        await self._call_service(
            "update_item", item=item.uid or item.summary, rename=item.summary
        )

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Forward delete as ``todo.remove_item``."""
        await self._call_service("remove_item", item=uids)
