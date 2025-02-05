"""Todo platform for the Cookidoo integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cookidoo_api import (
    CookidooAdditionalItem,
    CookidooException,
    CookidooIngredientItem,
)

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CookidooConfigEntry, CookidooDataUpdateCoordinator
from .entity import CookidooBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CookidooConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the todo list from a config entry created in the integrations UI."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        [
            CookidooIngredientsTodoListEntity(coordinator),
            CookidooAdditionalItemTodoListEntity(coordinator),
        ]
    )


class CookidooIngredientsTodoListEntity(CookidooBaseEntity, TodoListEntity):
    """A To-do List representation of the ingredients in the Cookidoo Shopping List."""

    _attr_translation_key = "ingredient_list"
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, coordinator: CookidooDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        assert coordinator.config_entry.unique_id
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_ingredients"

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the todo ingredients."""
        return [
            TodoItem(
                uid=item.id,
                summary=item.name,
                description=item.description or "",
                status=(
                    TodoItemStatus.COMPLETED
                    if item.is_owned
                    else TodoItemStatus.NEEDS_ACTION
                ),
            )
            for item in self.coordinator.data.ingredient_items
        ]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an ingredient to the To-do list.

        Cookidoo ingredients can be changed in state, but not in summary or description. This is currently not possible to distinguish in home assistant and just fails silently.
        """
        try:
            if TYPE_CHECKING:
                assert item.uid
            await self.coordinator.cookidoo.edit_ingredient_items_ownership(
                [
                    CookidooIngredientItem(
                        id=item.uid,
                        name="",
                        description="",
                        is_owned=item.status == TodoItemStatus.COMPLETED,
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
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, coordinator: CookidooDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        assert coordinator.config_entry.unique_id
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_additional_items"

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the todo items."""

        return [
            TodoItem(
                uid=item.id,
                summary=item.name,
                status=(
                    TodoItemStatus.COMPLETED
                    if item.is_owned
                    else TodoItemStatus.NEEDS_ACTION
                ),
            )
            for item in self.coordinator.data.additional_items
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""

        try:
            if TYPE_CHECKING:
                assert item.summary
            await self.coordinator.cookidoo.add_additional_items([item.summary])
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
            if TYPE_CHECKING:
                assert item.uid
                assert item.summary
            new_item = CookidooAdditionalItem(
                id=item.uid,
                name=item.summary,
                is_owned=item.status == TodoItemStatus.COMPLETED,
            )
            await self.coordinator.cookidoo.edit_additional_items_ownership([new_item])
            await self.coordinator.cookidoo.edit_additional_items([new_item])
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
            await self.coordinator.cookidoo.remove_additional_items(uids)
        except CookidooException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="todo_delete_item_failed",
                translation_placeholders={"count": str(len(uids))},
            ) from e

        await self.coordinator.async_refresh()
