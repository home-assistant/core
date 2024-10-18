"""Todo platform for the Cookidoo integration."""

from __future__ import annotations

from cookidoo_api import CookidooException, CookidooItem

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TODO_ADDITIONAL_ITEMS, TODO_ITEMS
from .coordinator import CookidooConfigEntry, CookidooDataUpdateCoordinator
from .entity import CookidooBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CookidooConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the todo list from a config entry created in the integrations UI."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        [
            CookidooItemTodoListEntity(coordinator),
            CookidooAdditionalItemTodoListEntity(coordinator),
        ]
    )


class CookidooItemTodoListEntity(CookidooBaseEntity, TodoListEntity):
    """A To-do List representation of the items in the Cookidoo Shopping List."""

    _attr_translation_key = "item_list"
    _attr_name = "Items"
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, coordinator: CookidooDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_items"

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the todo items."""
        return [
            TodoItem(
                uid=item["id"],
                summary=item["label"],
                description=item["description"] or "",
                status=TodoItemStatus.NEEDS_ACTION
                if item["state"] == "pending"
                else TodoItemStatus.COMPLETED,
            )
            for item in self.coordinator.data[TODO_ITEMS]
        ]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item to the To-do list.

        Cookidoo items can be changed in state, but not in summary or description. This is currently not possible to distinguish in home assistant and just fails silently.
        """
        try:
            assert item.uid
            await self.coordinator.cookidoo.update_items(
                [
                    CookidooItem(
                        {
                            "id": item.uid,
                            "label": "<nil>",
                            "description": "<nil>",
                            "state": "pending"
                            if item.status == TodoItemStatus.NEEDS_ACTION
                            else "checked",
                        }
                    )
                ]
            )
        except CookidooException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="todo_update_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        await self.coordinator.async_refresh()


class CookidooAdditionalItemTodoListEntity(CookidooBaseEntity, TodoListEntity):
    """A To-do List representation of the additional items in the Cookidoo Shopping List."""

    _attr_translation_key = "additional_item_list"
    _attr_name = "Additional Items"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, coordinator: CookidooDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_additional_items"

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the todo items."""
        return [
            TodoItem(
                uid=item["id"],
                summary=item["label"],
                status=TodoItemStatus.NEEDS_ACTION
                if item["state"] == "pending"
                else TodoItemStatus.COMPLETED,
            )
            for item in self.coordinator.data[TODO_ADDITIONAL_ITEMS]
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        try:
            assert item.summary
            await self.coordinator.cookidoo.create_additional_items([item.summary])
        except CookidooException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="todo_save_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item to the To-do list."""
        try:
            assert item.uid
            assert item.summary
            await self.coordinator.cookidoo.update_additional_items(
                [
                    CookidooItem(
                        {
                            "id": item.uid,
                            "label": item.summary,
                            "description": None,
                            "state": "pending"
                            if item.status == TodoItemStatus.NEEDS_ACTION
                            else "checked",
                        }
                    )
                ]
            )
        except CookidooException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="todo_update_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete an item from the To-do list."""

        try:
            await self.coordinator.cookidoo.delete_additional_items(uids)
        except CookidooException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="todo_delete_item_failed",
                translation_placeholders={"count": str(len(uids))},
            ) from e

        await self.coordinator.async_refresh()
