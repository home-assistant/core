"""Todo platform for the Bring! integration."""
from __future__ import annotations

from typing import TYPE_CHECKING

from python_bring_api.exceptions import BringRequestException

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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BringData, BringDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry created in the integrations UI."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    unique_id = config_entry.unique_id

    if TYPE_CHECKING:
        assert unique_id

    async_add_entities(
        BringTodoListEntity(
            coordinator,
            bring_list=bring_list,
            unique_id=unique_id,
        )
        for bring_list in coordinator.data.values()
    )


class BringTodoListEntity(
    CoordinatorEntity[BringDataUpdateCoordinator], TodoListEntity
):
    """A To-do List representation of the Bring! Shopping List."""

    _attr_icon = "mdi:cart"
    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(
        self,
        coordinator: BringDataUpdateCoordinator,
        bring_list: BringData,
        unique_id: str,
    ) -> None:
        """Initialize BringTodoListEntity."""
        super().__init__(coordinator)
        self._list_uuid = bring_list["listUuid"]
        self._attr_name = bring_list["name"]
        self._attr_unique_id = f"{unique_id}_{self._list_uuid}"

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the todo items."""
        return [
            TodoItem(
                uid=item["name"],
                summary=item["name"],
                description=item["specification"] or "",
                status=TodoItemStatus.NEEDS_ACTION,
            )
            for item in self.bring_list["items"]
        ]

    @property
    def bring_list(self) -> BringData:
        """Return the bring list."""
        return self.coordinator.data[self._list_uuid]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        try:
            await self.coordinator.bring.saveItemAsync(
                self.bring_list["listUuid"], item.summary, item.description or ""
            )
        except BringRequestException as e:
            raise HomeAssistantError("Unable to save todo item for bring") from e

        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item to the To-do list.

        Bring has an internal 'recent' list which we want to use instead of a todo list
        status, therefore completed todo list items will directly be deleted

        This results in following behaviour:

        - Completed items will move to the "completed" section in home assistant todo
            list and get deleted in bring, which will remove them from the home
            assistant todo list completely after a short delay
        - Bring items do not have unique identifiers and are using the
            name/summery/title. Therefore the name is not to be changed! Should a name
            be changed anyway, a new item will be created instead and no update for
            this item is performed and on the next cloud pull update, it will get
            cleared
        """

        bring_list = self.bring_list

        if TYPE_CHECKING:
            assert item.uid

        if item.status == TodoItemStatus.COMPLETED:
            await self.coordinator.bring.removeItemAsync(
                bring_list["listUuid"],
                item.uid,
            )

        elif item.summary == item.uid:
            try:
                await self.coordinator.bring.updateItemAsync(
                    bring_list["listUuid"],
                    item.uid,
                    item.description or "",
                )
            except BringRequestException as e:
                raise HomeAssistantError("Unable to update todo item for bring") from e
        else:
            try:
                await self.coordinator.bring.removeItemAsync(
                    bring_list["listUuid"],
                    item.uid,
                )
                await self.coordinator.bring.saveItemAsync(
                    bring_list["listUuid"],
                    item.summary,
                    item.description or "",
                )
            except BringRequestException as e:
                raise HomeAssistantError("Unable to replace todo item for bring") from e

        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete an item from the To-do list."""
        for uid in uids:
            try:
                await self.coordinator.bring.removeItemAsync(
                    self.bring_list["listUuid"], uid
                )
            except BringRequestException as e:
                raise HomeAssistantError("Unable to delete todo item for bring") from e

        await self.coordinator.async_refresh()
