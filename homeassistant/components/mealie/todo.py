"""Todo platform for Mealie."""

from __future__ import annotations

from aiomealie import MealieError, MutateShoppingItem, ShoppingItem, ShoppingList

from homeassistant.components.todo import (
    DOMAIN as TODO_DOMAIN,
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MealieConfigEntry, MealieShoppingListCoordinator
from .entity import MealieEntity

PARALLEL_UPDATES = 0
TODO_STATUS_MAP = {
    False: TodoItemStatus.NEEDS_ACTION,
    True: TodoItemStatus.COMPLETED,
}
TODO_STATUS_MAP_INV = {v: k for k, v in TODO_STATUS_MAP.items()}


def _convert_api_item(item: ShoppingItem) -> TodoItem:
    """Convert Mealie shopping list items into a TodoItem."""

    return TodoItem(
        summary=item.display,
        uid=item.item_id,
        status=TODO_STATUS_MAP.get(
            item.checked,
            TodoItemStatus.NEEDS_ACTION,
        ),
        due=None,
        description=None,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MealieConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the todo platform for entity."""
    coordinator = entry.runtime_data.shoppinglist_coordinator

    added_lists: set[str] = set()

    assert entry.unique_id is not None

    def _async_delete_entities(lists: set[str]) -> None:
        """Delete entities for removed shopping lists."""
        entity_registry = er.async_get(hass)
        for list_id in lists:
            entity_id = entity_registry.async_get_entity_id(
                TODO_DOMAIN, DOMAIN, f"{entry.unique_id}_{list_id}"
            )
            if entity_id:
                entity_registry.async_remove(entity_id)

    def _async_entity_listener() -> None:
        """Handle additions/deletions of shopping lists."""
        received_lists = set(coordinator.data)
        new_lists = received_lists - added_lists
        removed_lists = added_lists - received_lists
        if new_lists:
            async_add_entities(
                MealieShoppingListTodoListEntity(coordinator, shopping_list_id)
                for shopping_list_id in new_lists
            )
            added_lists.update(new_lists)
        if removed_lists:
            _async_delete_entities(removed_lists)

    coordinator.async_add_listener(_async_entity_listener)
    _async_entity_listener()


class MealieShoppingListTodoListEntity(MealieEntity, TodoListEntity):
    """A todo list entity."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
    )

    _attr_translation_key = "shopping_list"

    coordinator: MealieShoppingListCoordinator

    def __init__(
        self, coordinator: MealieShoppingListCoordinator, shopping_list_id: str
    ) -> None:
        """Create the todo entity."""
        super().__init__(coordinator, shopping_list_id)
        self._shopping_list_id = shopping_list_id
        self._attr_name = self.shopping_list.name

    @property
    def shopping_list(self) -> ShoppingList:
        """Get the shopping list."""
        return self.coordinator.data[self._shopping_list_id].shopping_list

    @property
    def shopping_items(self) -> list[ShoppingItem]:
        """Get the shopping items for this list."""
        return self.coordinator.data[self._shopping_list_id].items

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Get the current set of To-do items."""
        return [_convert_api_item(item) for item in self.shopping_items]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the list."""
        position = 0
        if len(self.shopping_items) > 0:
            position = self.shopping_items[-1].position + 1

        new_shopping_item = MutateShoppingItem(
            list_id=self._shopping_list_id,
            note=item.summary.strip() if item.summary else item.summary,
            position=position,
        )
        try:
            await self.coordinator.client.add_shopping_item(new_shopping_item)
        except MealieError as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="add_item_error",
                translation_placeholders={
                    "shopping_list_name": self.shopping_list.name
                },
            ) from exception
        finally:
            await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item on the list."""
        list_items = self.shopping_items

        list_item: ShoppingItem | None = next(
            (x for x in list_items if x.item_id == item.uid), None
        )
        assert list_item is not None
        position = list_item.position

        update_shopping_item = MutateShoppingItem(
            item_id=list_item.item_id,
            list_id=list_item.list_id,
            note=list_item.note,
            display=list_item.display,
            checked=item.status == TodoItemStatus.COMPLETED,
            position=position,
            is_food=list_item.is_food,
            disable_amount=list_item.disable_amount,
            quantity=list_item.quantity,
            label_id=list_item.label_id,
            food_id=list_item.food_id,
            unit_id=list_item.unit_id,
        )

        stripped_item_summary = item.summary.strip() if item.summary else item.summary

        if list_item.display.strip() != stripped_item_summary:
            update_shopping_item.note = stripped_item_summary
            update_shopping_item.position = position
            update_shopping_item.is_food = False
            update_shopping_item.food_id = None
            update_shopping_item.quantity = 0.0
            update_shopping_item.checked = item.status == TodoItemStatus.COMPLETED

        try:
            await self.coordinator.client.update_shopping_item(
                list_item.item_id, update_shopping_item
            )
        except MealieError as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_item_error",
                translation_placeholders={
                    "shopping_list_name": self.shopping_list.name
                },
            ) from exception
        finally:
            await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete items from the list."""
        try:
            for uid in uids:
                await self.coordinator.client.delete_shopping_item(uid)
        except MealieError as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="delete_item_error",
                translation_placeholders={
                    "shopping_list_name": self.shopping_list.name
                },
            ) from exception
        finally:
            await self.coordinator.async_refresh()

    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Re-order an item on the list."""
        if uid == previous_uid:
            return
        list_items: list[ShoppingItem] = self.shopping_items

        item_idx = {itm.item_id: idx for idx, itm in enumerate(list_items)}
        if uid not in item_idx:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="item_not_found_error",
                translation_placeholders={"shopping_list_item": uid},
            )
        if previous_uid and previous_uid not in item_idx:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="item_not_found_error",
                translation_placeholders={"shopping_list_item": previous_uid},
            )
        dst_idx = item_idx[previous_uid] + 1 if previous_uid else 0
        src_idx = item_idx[uid]
        src_item = list_items.pop(src_idx)
        if dst_idx > src_idx:
            dst_idx -= 1
        list_items.insert(dst_idx, src_item)

        for position, item in enumerate(list_items):
            mutate_shopping_item = MutateShoppingItem()
            mutate_shopping_item.list_id = item.list_id
            mutate_shopping_item.item_id = item.item_id
            mutate_shopping_item.position = position
            mutate_shopping_item.is_food = item.is_food
            mutate_shopping_item.quantity = item.quantity
            mutate_shopping_item.label_id = item.label_id
            mutate_shopping_item.note = item.note
            mutate_shopping_item.checked = item.checked

            if item.is_food:
                mutate_shopping_item.food_id = item.food_id
                mutate_shopping_item.unit_id = item.unit_id

            await self.coordinator.client.update_shopping_item(
                mutate_shopping_item.item_id, mutate_shopping_item
            )

        await self.coordinator.async_refresh()

    @property
    def available(self) -> bool:
        """Return False if shopping list no longer available."""
        return super().available and self._shopping_list_id in self.coordinator.data
