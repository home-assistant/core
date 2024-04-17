"""A shopping list todo platform."""

from typing import cast

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NoMatchingShoppingListItem, ShoppingData
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the shopping_list todo platform."""
    shopping_data = hass.data[DOMAIN]
    entity = ShoppingTodoListEntity(shopping_data, unique_id=config_entry.entry_id)
    async_add_entities([entity], True)


class ShoppingTodoListEntity(TodoListEntity):
    """A To-do List representation of the Shopping List."""

    _attr_has_entity_name = True
    _attr_translation_key = "shopping_list"
    _attr_should_poll = False
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
    )

    def __init__(self, data: ShoppingData, unique_id: str) -> None:
        """Initialize ShoppingTodoListEntity."""
        self._attr_unique_id = unique_id
        self._data = data

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        await self._data.async_add(
            item.summary, complete=(item.status == TodoItemStatus.COMPLETED)
        )

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item to the To-do list."""
        data = {
            "name": item.summary,
            "complete": item.status == TodoItemStatus.COMPLETED,
        }
        try:
            await self._data.async_update(item.uid, data)
        except NoMatchingShoppingListItem as err:
            raise HomeAssistantError(
                f"Shopping list item '{item.uid}' was not found"
            ) from err

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Add an item to the To-do list."""
        await self._data.async_remove_items(set(uids))

    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Re-order an item to the To-do list."""

        try:
            await self._data.async_move_item(uid, previous_uid)
        except NoMatchingShoppingListItem as err:
            raise HomeAssistantError(
                f"Shopping list item '{uid}' could not be re-ordered"
            ) from err

    async def async_added_to_hass(self) -> None:
        """Entity has been added to hass."""
        # Shopping list integration doesn't currently support config entry unload
        # so this code may not be used in practice, however it is here in case
        # this changes in the future.
        self.async_on_remove(self._data.async_add_listener(self.async_write_ha_state))

    @property
    def todo_items(self) -> list[TodoItem]:
        """Get items in the To-do list."""
        results = []
        for item in self._data.items:
            if cast(bool, item["complete"]):
                status = TodoItemStatus.COMPLETED
            else:
                status = TodoItemStatus.NEEDS_ACTION
            results.append(
                TodoItem(
                    summary=cast(str, item["name"]),
                    uid=cast(str, item["id"]),
                    status=status,
                )
            )
        return results
