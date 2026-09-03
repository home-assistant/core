"""Todo platform for the Famn integration."""

from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING, override
from uuid import UUID

from famn_sdk import ApiError, CreateTaskItemRequest, ListItem, TaskItem

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, TASK_TYPE_TODOS
from .coordinator import FamnChoresCoordinator, FamnConfigEntry, FamnShoppingCoordinator
from .entity import FamnEntity, famn_device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FamnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the todo platform from a config entry."""
    coordinator = entry.runtime_data.chores
    known_lists: set[str] = set()

    @callback
    def add_entities() -> None:
        """Add todo entities for chore lists that appeared in Famn."""
        if new_lists := set(coordinator.data) - known_lists:
            async_add_entities(
                FamnChoreListEntity(coordinator, list_id) for list_id in new_lists
            )
            known_lists.update(new_lists)

    entry.async_on_unload(coordinator.async_add_listener(add_entities))
    add_entities()

    shopping = entry.runtime_data.shopping
    known_shopping: set[str] = set()

    @callback
    def add_shopping_entities() -> None:
        """Add todo entities for shopping lists that appeared in Famn."""
        if new_lists := set(shopping.data) - known_shopping:
            async_add_entities(
                FamnShoppingListEntity(shopping, list_id) for list_id in new_lists
            )
            known_shopping.update(new_lists)

    entry.async_on_unload(shopping.async_add_listener(add_shopping_entities))
    add_shopping_entities()


class FamnShoppingListEntity(
    CoordinatorEntity[FamnShoppingCoordinator], TodoListEntity
):
    """A todo list representation of a Famn shopping list.

    Items can be added (also via Assist: "add milk to the shopping list")
    and checked off; whoever is in the store sees changes instantly in the
    Famn app and vice versa.
    """

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, coordinator: FamnShoppingCoordinator, list_id: str) -> None:
        """Initialize the shopping list entity."""
        super().__init__(coordinator)

        unique_id = coordinator.config_entry.unique_id
        if TYPE_CHECKING:
            assert unique_id is not None

        self._key = list_id
        self._attr_unique_id = f"{unique_id}_{list_id}"
        self._attr_name = coordinator.data[list_id].shopping_list.name
        self._attr_device_info = famn_device_info(coordinator.config_entry)

    @property
    @override
    def available(self) -> bool:
        """Return if the underlying Famn list still exists."""
        return super().available and self._key in self.coordinator.data

    @property
    @override
    def todo_items(self) -> list[TodoItem]:
        """Return the open items on the list."""
        return [
            TodoItem(
                uid=item.id,
                summary=item.name,
                description=item.description,
                status=TodoItemStatus.NEEDS_ACTION,
            )
            for item in sorted(
                self.coordinator.data[self._key].items,
                key=lambda item: (item.sort_order or 0, item.name),
            )
            if item.id is not None and item.done_at is None
        ]

    @override
    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the shopping list."""
        try:
            await self.coordinator.auth.async_ensure_token_valid()
            await self.coordinator.list_item_api.create_list_item_endpoint(
                self._key,
                body=ListItem(
                    list_id=UUID(self._key),
                    name=item.summary or "",
                    description=item.description,
                ),
                combine_same_items=True,
            )
        except ApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="create_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from err

        await self.coordinator.async_request_refresh()

    def _famn_item(self, uid: str | None) -> ListItem | None:
        """Return the Famn list item a todo item stands for."""
        return next(
            (item for item in self.coordinator.data[self._key].items if item.id == uid),
            None,
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Keep the entity name in step with the list's name in Famn."""
        if (data := self.coordinator.data.get(self._key)) is not None:
            self._attr_name = data.shopping_list.name
        super()._handle_coordinator_update()

    @override
    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Edit the item, check it off, or both.

        Home Assistant merges the whole update into one item, so a single
        call can carry a rename and a completion together. Both are applied,
        the edit first so that Famn records the completion against the item
        as the user renamed it.
        """
        existing = self._famn_item(item.uid)
        if existing is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_item_failed",
                translation_placeholders={"name": item.summary or ""},
            )

        if item.summary != existing.name or item.description != existing.description:
            await self._async_edit(item, existing)
        if item.status == TodoItemStatus.COMPLETED:
            await self._async_check_off(item)

        await self.coordinator.async_request_refresh()

    async def _async_check_off(self, item: TodoItem) -> None:
        """Mark the item bought."""
        try:
            await self.coordinator.auth.async_ensure_token_valid()
            await self.coordinator.list_item_api.set_list_item_done_endpoint(
                self._key, str(item.uid)
            )
        except ApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="complete_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from err

    async def _async_edit(self, item: TodoItem, existing: ListItem) -> None:
        """Write a new name and description back to Famn.

        The endpoint replaces the whole item, so the edit is applied to the
        copy Famn last handed us. Sending a bare item instead would drop the
        product, category and quantity the app keeps on it.
        """
        try:
            await self.coordinator.auth.async_ensure_token_valid()
            await self.coordinator.list_item_api.update_list_item_endpoint(
                self._key,
                str(item.uid),
                body=replace(
                    existing,
                    name=item.summary or existing.name,
                    description=item.description,
                ),
            )
        except ApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from err


def _sort_key(item: TaskItem) -> tuple[datetime, int, str]:
    """Sort chores by occurrence or due date, then sort order, then title."""
    return (
        item.next_occurrence
        or item.due_date
        or datetime.max.replace(tzinfo=dt_util.UTC),
        item.sort_order or 0,
        item.title,
    )


class FamnChoreListEntity(FamnEntity, TodoListEntity):
    """A todo list representation of a Famn chore or todo list.

    Chore lists recur inside Famn and only support marking items done. Todo
    lists additionally support creating items, so an automation can put a
    one-off task in front of the family ("empty the washing machine") with
    Famn handling notifications and task XP.
    """

    def __init__(self, coordinator: FamnChoresCoordinator, list_id: str) -> None:
        """Initialize the todo list entity."""
        super().__init__(coordinator, list_id)
        task_list = coordinator.data[list_id].task_list
        self._attr_name = task_list.name

        # Chores recur on a rule Famn owns, so only their title can be
        # edited from here; one-off todos expose their details as well.
        self._edits_details = task_list.task_type == TASK_TYPE_TODOS

        features = TodoListEntityFeature.UPDATE_TODO_ITEM
        if self._edits_details:
            features |= (
                TodoListEntityFeature.CREATE_TODO_ITEM
                | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
                | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
            )
        self._attr_supported_features = features

    @property
    @override
    def todo_items(self) -> list[TodoItem]:
        """Return the open chores on the list."""
        return [
            TodoItem(
                uid=item.id,
                summary=item.title,
                description=item.description,
                due=item.due_date or item.next_occurrence,
                status=TodoItemStatus.NEEDS_ACTION,
            )
            for item in sorted(self.coordinator.data[self._key].items, key=_sort_key)
            if item.id is not None
        ]

    @override
    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a new todo in Famn.

        Famn assigns it to the space owner by default, whose app then
        notifies about it like any other task; completing it in the app
        grants task XP as usual.
        """
        try:
            await self.coordinator.auth.async_ensure_token_valid()
            await self.coordinator.tasks_api.create_task_item_endpoint(
                self._key,
                body=CreateTaskItemRequest(
                    title=item.summary or "",
                    description=item.description,
                    due_date=item.due if isinstance(item.due, datetime) else None,
                    task_list_id=self._key,
                ),
            )
        except ApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="create_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from err

        await self.coordinator.async_request_refresh()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Keep the entity name in step with the list's name in Famn."""
        if (data := self.coordinator.data.get(self._key)) is not None:
            self._attr_name = data.task_list.name
        super()._handle_coordinator_update()

    @override
    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Edit the chore, mark it done, or both.

        Home Assistant merges the whole update into one item, so a single
        call can carry a rename and a completion together. Both are applied,
        the edit first so that the completion Famn logs refers to the item as
        the user renamed it.
        """
        existing = next(
            (
                task_item
                for task_item in self.coordinator.data[self._key].items
                if task_item.id == item.uid
            ),
            None,
        )
        if existing is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_item_failed",
                translation_placeholders={"name": item.summary or ""},
            )

        if (updated := self._merged(item, existing)) != existing:
            await self._async_edit(item, updated)
        if item.status == TodoItemStatus.COMPLETED:
            await self._async_log_done(item)

        await self.coordinator.async_request_refresh()

    def _merged(self, item: TodoItem, existing: TaskItem) -> TaskItem:
        """Return the Famn task with the requested edits applied."""
        updated = replace(existing, title=item.summary or existing.title)
        if self._edits_details:
            # A chore's `due` is the next occurrence Famn computed, not a
            # stored deadline, so it is only written back for todo lists.
            updated = replace(
                updated,
                description=item.description,
                due_date=item.due if isinstance(item.due, datetime) else None,
            )
        return updated

    async def _async_log_done(self, item: TodoItem) -> None:
        """Log the chore as completed, which is what grants the XP."""
        try:
            await self.coordinator.auth.async_ensure_token_valid()
            await self.coordinator.tasks_api.log_task_item_done_endpoint(
                str(item.uid), self._key
            )
        except ApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="complete_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from err

    async def _async_edit(self, item: TodoItem, updated: TaskItem) -> None:
        """Write the item's new fields back to Famn.

        The endpoint replaces the whole task, so the edit is applied to the
        copy Famn last handed us; a bare item would drop the recurrence
        rule, assignments and category the app keeps on it.
        """
        try:
            await self.coordinator.auth.async_ensure_token_valid()
            await self.coordinator.tasks_api.update_task_item_endpoint(
                str(item.uid), self._key, body=updated
            )
        except ApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from err
