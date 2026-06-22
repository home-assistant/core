"""Platform for Alexa To-do integration."""

from typing import TYPE_CHECKING, override

from aioamazondevices.structures import (
    AmazonListInfo,
    AmazonListItemStatus,
    AmazonListType,
)

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.helpers.entity import EntityDescription

from .const import _LOGGER
from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator, alexa_api_call
from .entity import AmazonServiceEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Alexa To-do Lists platform."""
    coordinator = entry.runtime_data

    known_list_ids: set[str] = set()

    def _check_lists() -> None:
        current_list_ids = {todo_list.id for todo_list in coordinator.api.todo_lists}
        new_list_ids = current_list_ids - known_list_ids
        if new_list_ids:
            known_list_ids.update(new_list_ids)
            async_add_entities(
                [
                    AlexaToDoList(coordinator, alexa_list)
                    for alexa_list in coordinator.api.todo_lists
                    if alexa_list.id in new_list_ids
                ]
            )

    _check_lists()
    entry.async_on_unload(coordinator.async_add_listener(_check_lists))


class AlexaToDoList(AmazonServiceEntity, TodoListEntity):
    """Representation of an Alexa to-do list."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(
        self, coordinator: AmazonDevicesCoordinator, alexa_list: AmazonListInfo
    ) -> None:
        """Initialize an Alexa to-do list entity."""
        self._list = alexa_list

        if alexa_list.list_type == AmazonListType.CUSTOM:
            # Custom list -> Use actual name
            entity_description = EntityDescription(
                key=alexa_list.id, name=alexa_list.name
            )
        else:
            entity_description = EntityDescription(
                key=alexa_list.id,
                translation_key=alexa_list.list_type.value.lower(),
            )

        super().__init__(coordinator, entity_description)

        _LOGGER.debug(
            "Created todo entity for list: %s (ID: %s)", self._list.name, self._list.id
        )

    @property
    @override
    def todo_items(self) -> list[TodoItem]:
        """Return all to-do items in the list."""

        todo_items = self.coordinator.todo_list_items.get(self._list.id, {}).values()

        return [
            TodoItem(
                uid=item.id,
                summary=item.name,
                status=TodoItemStatus.COMPLETED
                if item.status == AmazonListItemStatus.COMPLETE
                else TodoItemStatus.NEEDS_ACTION,
            )
            for item in todo_items
        ]

    @override
    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        _LOGGER.debug(
            "Creating todo item: %s for list: %s", item.summary, self._list.name
        )

        # For passing type checking, existence of summary
        # is already checked by voluptuous
        if TYPE_CHECKING:
            assert item.summary is not None

        async with alexa_api_call(self.coordinator):
            await self.coordinator.api.add_todo_list_item(self._list.id, item.summary)

        _LOGGER.debug(
            "Successfully created todo item: %s for list: %s",
            item.summary,
            self._list.name,
        )

    @override
    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete items from the to-do list."""
        _LOGGER.debug("Called async_delete_todo_items for %s item(s)", len(uids))

        list_items_lookup = self.coordinator.todo_list_items[self._list.id]

        for uid in uids:
            existing_item = list_items_lookup[uid]

            _LOGGER.debug(
                "Deleting item %s (ID: %s) with version %s",
                existing_item.name,
                uid,
                existing_item.version,
            )
            async with alexa_api_call(self.coordinator):
                await self.coordinator.api.delete_todo_list_item(
                    self._list.id, uid, existing_item.version
                )
            _LOGGER.debug(
                "Successfully deleted item %s (ID: %s) with version %s",
                existing_item.name,
                uid,
                existing_item.version,
            )

    @override
    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item in the To-do list."""
        list_items_lookup = self.coordinator.todo_list_items[self._list.id]

        # For passing type checking, existence of UID and summary
        # is already checked by voluptuous
        if TYPE_CHECKING:
            assert item.uid is not None
            assert item.summary is not None

        existing_item = list_items_lookup[item.uid]

        if has_completed_changed := (
            existing_item.status == AmazonListItemStatus.COMPLETE
        ) != (item.status == TodoItemStatus.COMPLETED):
            # Update the checked status
            _LOGGER.debug(
                "Updating item %s with checked status %s", item.uid, item.status
            )

            async with alexa_api_call(self.coordinator):
                await self.coordinator.api.set_todo_list_item_checked_status(
                    self._list.id,
                    item.uid,
                    item.status == TodoItemStatus.COMPLETED,
                    existing_item.version,
                )

            _LOGGER.debug(
                "Successfully updated item %s with checked status %s",
                item.uid,
                item.status,
            )

        if existing_item.name != item.summary:
            # Name has changed, update it
            _LOGGER.debug("Updating item %s with new name %s", item.uid, item.summary)

            # If both have changed -> Increase item version by 1
            version = existing_item.version + int(has_completed_changed)

            async with alexa_api_call(self.coordinator):
                await self.coordinator.api.rename_todo_list_item(
                    self._list.id, item.uid, item.summary, version
                )
            _LOGGER.debug(
                "Successfully updated item %s with new name %s", item.uid, item.summary
            )
