"""Todo platform for the Bring! integration."""

from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING
import uuid

from bring_api import (
    BringItem,
    BringItemOperation,
    BringList,
    BringNotificationType,
    BringRequestException,
)
import voluptuous as vol

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_ITEM_NAME,
    ATTR_NOTIFICATION_TYPE,
    DOMAIN,
    SERVICE_PUSH_NOTIFICATION,
)
from .coordinator import BringConfigEntry, BringData, BringDataUpdateCoordinator
from .entity import BringBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry created in the integrations UI."""
    coordinator = config_entry.runtime_data
    lists_added: set[str] = set()

    @callback
    def add_entities() -> None:
        """Add or remove todo list entities."""
        nonlocal lists_added

        if new_lists := {lst.listUuid for lst in coordinator.lists} - lists_added:
            async_add_entities(
                BringTodoListEntity(coordinator, bring_list)
                for bring_list in coordinator.lists
                if bring_list.listUuid in new_lists
            )
            lists_added |= new_lists

    coordinator.async_add_listener(add_entities)
    add_entities()

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_PUSH_NOTIFICATION,
        {
            vol.Required(ATTR_NOTIFICATION_TYPE): vol.All(
                vol.Upper, vol.Coerce(BringNotificationType)
            ),
            vol.Optional(ATTR_ITEM_NAME): cv.string,
        },
        "async_send_message",
    )


class BringTodoListEntity(BringBaseEntity, TodoListEntity):
    """A To-do List representation of the Bring! Shopping List."""

    _attr_translation_key = "shopping_list"
    _attr_name = None
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(
        self, coordinator: BringDataUpdateCoordinator, bring_list: BringList
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, bring_list)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{self._list_uuid}"

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the todo items."""
        return [
            *(
                TodoItem(
                    uid=item.uuid,
                    summary=item.itemId,
                    description=item.specification,
                    status=TodoItemStatus.NEEDS_ACTION,
                )
                for item in self.bring_list.content.items.purchase
            ),
            *(
                TodoItem(
                    uid=item.uuid,
                    summary=item.itemId,
                    description=item.specification,
                    status=TodoItemStatus.COMPLETED,
                )
                for item in self.bring_list.content.items.recently
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
                self._list_uuid,
                item.summary or "",
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

        current_item = next(
            (
                i
                for i in chain(
                    bring_list.content.items.purchase, bring_list.content.items.recently
                )
                if i.uuid == item.uid
            ),
            None,
        )

        if TYPE_CHECKING:
            assert item.uid
            assert current_item

        if item.summary == current_item.itemId:
            try:
                await self.coordinator.bring.batch_update_list(
                    self._list_uuid,
                    BringItem(
                        itemId=item.summary or "",
                        spec=item.description or "",
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
                    self._list_uuid,
                    [
                        BringItem(
                            itemId=current_item.itemId,
                            spec=item.description or "",
                            uuid=item.uid,
                            operation=BringItemOperation.REMOVE,
                        ),
                        BringItem(
                            itemId=item.summary or "",
                            spec=item.description or "",
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
                self._list_uuid,
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

    async def async_send_message(
        self,
        message: BringNotificationType,
        item: str | None = None,
    ) -> None:
        """Send a push notification to members of a shared bring list."""

        try:
            await self.coordinator.bring.notify(self._list_uuid, message, item or None)
        except BringRequestException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="notify_request_failed",
            ) from e
        except ValueError as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="notify_missing_argument",
                translation_placeholders={"field": "item"},
            ) from e
