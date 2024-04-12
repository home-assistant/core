"""A todo platform for OurGroceries."""

import asyncio
from typing import Any

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
from .coordinator import OurGroceriesDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the OurGroceries todo platform config entry."""
    coordinator: OurGroceriesDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        OurGroceriesTodoListEntity(coordinator, sl["id"], sl["name"])
        for sl in coordinator.lists
    )


def _completion_status(item: dict[str, Any]) -> TodoItemStatus:
    if item.get("crossedOffAt", False):
        return TodoItemStatus.COMPLETED
    return TodoItemStatus.NEEDS_ACTION


class OurGroceriesTodoListEntity(
    CoordinatorEntity[OurGroceriesDataUpdateCoordinator], TodoListEntity
):
    """An OurGroceries TodoListEntity."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(
        self,
        coordinator: OurGroceriesDataUpdateCoordinator,
        list_id: str,
        list_name: str,
    ) -> None:
        """Initialize TodoistTodoListEntity."""
        super().__init__(coordinator=coordinator)
        self._list_id = list_id
        self._attr_unique_id = list_id
        self._attr_name = list_name

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is None:
            self._attr_todo_items = None
        else:
            self._attr_todo_items = [
                TodoItem(
                    summary=item["name"],
                    uid=item["id"],
                    status=_completion_status(item),
                )
                for item in self.coordinator.data[self._list_id]["list"]["items"]
            ]
        super()._handle_coordinator_update()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a To-do item."""
        if item.status != TodoItemStatus.NEEDS_ACTION:
            raise ValueError("Only active tasks may be created.")
        await self.coordinator.og.add_item_to_list(
            self._list_id, item.summary, auto_category=True
        )
        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        if item.summary:
            api_items = self.coordinator.data[self._list_id]["list"]["items"]
            category = next(
                api_item.get("categoryId")
                for api_item in api_items
                if api_item["id"] == item.uid
            )
            await self.coordinator.og.change_item_on_list(
                self._list_id, item.uid, category, item.summary
            )
        if item.status is not None:
            cross_off = item.status == TodoItemStatus.COMPLETED
            await self.coordinator.og.toggle_item_crossed_off(
                self._list_id, item.uid, cross_off=cross_off
            )
        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete a To-do item."""
        await asyncio.gather(
            *[
                self.coordinator.og.remove_item_from_list(self._list_id, uid)
                for uid in uids
            ]
        )
        await self.coordinator.async_refresh()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass update state from existing coordinator data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
