"""Todo platform for the Bring! integration."""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from bring_api.exceptions import BringRequestException
from bring_api.types import BringItem, BringItemOperation

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

    _attr_translation_key = "shopping_list"
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
            *(
                TodoItem(
                    uid=item["uuid"],
                    summary=item["itemId"],
                    description=item["specification"] or "",
                    status=TodoItemStatus.NEEDS_ACTION,
                )
                for item in self.bring_list["purchase_items"]
            ),
            *(
                TodoItem(
                    uid=item["uuid"],
                    summary=item["itemId"],
                    description=item["specification"] or "",
                    status=TodoItemStatus.COMPLETED,
                )
                for item in self.bring_list["recently_items"]
            ),
        ]

    @property
    def bring_list(self) -> BringData:
        """Return the bring list."""
        return self.coordinator.data[self._list_uuid]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        try:
            await self.coordinator.bring.save_item(
                self.bring_list["listUuid"],
                item.summary,
                item.description or "",
                str(uuid.uuid4()),
            )
        except BringRequestException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="todo_save_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item to the To-do list.

        Bring has an internal 'recent' list which we want to use instead of a todo list
        status, therefore completed todo list items are matched to the recent list and
        pending items to the purchase list.

        This results in following behaviour:

        - Completed items will move to the "completed" section in home assistant todo
            list and get moved to the recently list in bring
        - Bring shows some odd behaviour when renaming items. This is because Bring
            did not have unique identifiers for items in the past and this is still
            a relic from it. Therefore the name is not to be changed! Should a name
            be changed anyway, the item will be deleted and a new item will be created
            instead and no update for this item is performed and on the next cloud pull
            update, it will get cleared and replaced seamlessly.
        """

        bring_list = self.bring_list

        bring_purchase_item = next(
            (i for i in bring_list["purchase_items"] if i["uuid"] == item.uid),
            None,
        )

        bring_recently_item = next(
            (i for i in bring_list["recently_items"] if i["uuid"] == item.uid),
            None,
        )

        current_item = bring_purchase_item or bring_recently_item

        if TYPE_CHECKING:
            assert item.uid
            assert current_item

        if item.summary == current_item["itemId"]:
            try:
                await self.coordinator.bring.batch_update_list(
                    bring_list["listUuid"],
                    BringItem(
                        itemId=item.summary,
                        spec=item.description,
                        uuid=item.uid,
                    ),
                    BringItemOperation.ADD
                    if item.status == TodoItemStatus.NEEDS_ACTION
                    else BringItemOperation.COMPLETE,
                )
            except BringRequestException as e:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="todo_update_item_failed",
                    translation_placeholders={"name": item.summary or ""},
                ) from e
        else:
            try:
                await self.coordinator.bring.batch_update_list(
                    bring_list["listUuid"],
                    [
                        BringItem(
                            itemId=current_item["itemId"],
                            spec=item.description,
                            uuid=item.uid,
                            operation=BringItemOperation.REMOVE,
                        ),
                        BringItem(
                            itemId=item.summary,
                            spec=item.description,
                            uuid=str(uuid.uuid4()),
                            operation=BringItemOperation.ADD
                            if item.status == TodoItemStatus.NEEDS_ACTION
                            else BringItemOperation.COMPLETE,
                        ),
                    ],
                )

            except BringRequestException as e:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="todo_rename_item_failed",
                    translation_placeholders={"name": item.summary or ""},
                ) from e

        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete an item from the To-do list."""

        try:
            await self.coordinator.bring.batch_update_list(
                self.bring_list["listUuid"],
                [
                    BringItem(
                        itemId=uid,
                        spec="",
                        uuid=uid,
                    )
                    for uid in uids
                ],
                BringItemOperation.REMOVE,
            )
        except BringRequestException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="todo_delete_item_failed",
                translation_placeholders={"count": str(len(uids))},
            ) from e

        await self.coordinator.async_refresh()
