"""Platform for Alexa To-do integration."""

import logging
from typing import TYPE_CHECKING

from aioamazondevices.const.todo import LIST_TYPE_SHOP
from aioamazondevices.implementation.todo import is_item_complete

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import EntityDescription

from .const import DOMAIN
from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator
from .entity import AmazonServiceEntity

if TYPE_CHECKING:
    from aioamazondevices.structures import ListInfo, ListItem

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Alexa To-do Lists platform.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry.
        async_add_entities: The callback to add entities.

    """
    coordinator = entry.runtime_data

    available_lists: list[ListInfo] = coordinator.api.todo_lists

    async_add_entities(
        [AlexaToDoList(coordinator, alexa_list) for alexa_list in available_lists]
    )


class AlexaToDoList(AmazonServiceEntity, TodoListEntity):
    """Representation of an Alexa To-do List."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(
        self, coordinator: AmazonDevicesCoordinator, alexa_list: ListInfo
    ) -> None:
        """Initialize an AlexaTodoList.

        Args:
            coordinator: The coordinator for this entity.
            alexa_list: The Alexa list information.

        """
        self._coordinator: AmazonDevicesCoordinator = coordinator
        self._list: ListInfo = alexa_list

        self._attr_unique_id = alexa_list.id
        self._attr_name = alexa_list.name

        self._attr_translation_key = (
            "shop" if alexa_list.list_type == LIST_TYPE_SHOP else "todo"
        )

        super().__init__(
            coordinator,
            EntityDescription(key=alexa_list.id, name=alexa_list.name),
        )

        _LOGGER.debug(
            "Created todo entity for list: %s (ID: %s)", self._list.name, self._list.id
        )

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """All Todo items in the list.

        Returns:
            List of TodoItems in the list.
        """
        todo_items: list[ListItem] = self._coordinator.todo_items.get(self._list.id, [])

        return [
            TodoItem(
                uid=item.id,
                summary=item.name,
                status=TodoItemStatus.COMPLETED
                if is_item_complete(item)
                else TodoItemStatus.NEEDS_ACTION,
            )
            for item in todo_items
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list.

        Args:
            item: The item to add.

        Raises:
            ServiceValidationError: If the item summary is missing.

        """
        _LOGGER.debug(
            "Creating todo item: %s for list: %s", item.summary, self._list.name
        )

        if not item.summary:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="exceptions.todo_item_summary_empty",
            )

        await self._coordinator.api.add_todo_list_item(self._list.id, item.summary)

        _LOGGER.debug(
            "Successfully created todo item: %s for list: %s",
            item.summary,
            self._list.name,
        )

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete items from the to-do list.

        Args:
            uids: The unique IDs of the items to delete.

        """
        _LOGGER.debug("Called async_delete_todo_items for %s item(s)", len(uids))

        list_items_lookup = self._coordinator.todo_items_lookup.get(self._list.id)

        if list_items_lookup is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="exceptions.todo_items_lookup_not_found",
                translation_placeholders={"list_name": self._list.name},
            )

        for uid in uids:
            existing_item = list_items_lookup.get(uid)

            if existing_item is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="exceptions.todo_item_not_found",
                    translation_placeholders={
                        "uid": uid,
                        "list_name": self._list.name,
                    },
                )
            _LOGGER.debug(
                "Deleting item %s (ID: %s) with version %s",
                existing_item.name,
                uid,
                existing_item.version,
            )
            await self._coordinator.api.delete_todo_list_item(
                self._list.id, uid, existing_item.version
            )
            _LOGGER.debug(
                "Successfully deleted item %s (ID: %s) with version %s",
                existing_item.name,
                uid,
                existing_item.version,
            )

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item in the To-do list.

        Args:
            item: The item to update.

        Raises:
            ServiceValidationError: If the item summary or UID is missing.

        """
        if not item.summary or not item.uid:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="exceptions.todo_item_summary_uid_required",
            )

        list_items_lookup = self._coordinator.todo_items_lookup.get(self._list.id)

        if list_items_lookup is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="exceptions.todo_items_lookup_not_found",
                translation_placeholders={"list_name": self._list.name},
            )

        existing_item = list_items_lookup.get(item.uid)

        if existing_item is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="exceptions.todo_item_not_found",
                translation_placeholders={
                    "uid": item.uid,
                    "list_name": self._list.name,
                },
            )

        # Check what has changed
        has_completed_changed = is_item_complete(existing_item) != (
            item.status == TodoItemStatus.COMPLETED
        )
        has_summary_changed = existing_item.name != item.summary

        if has_completed_changed:
            # Update the checked status
            _LOGGER.debug(
                "Updating item %s with checked status %s", item.uid, item.status
            )

            await self._coordinator.api.set_todo_list_item_checked_status(
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

        if has_summary_changed:
            # Name has changed, update it
            _LOGGER.debug("Updating item %s with new name %s", item.uid, item.summary)

            if has_completed_changed:
                # Both has changed -> Item version increases, otherwise rejected by API
                version = existing_item.version + 1
            else:
                version = existing_item.version

            await self._coordinator.api.rename_todo_list_item(
                self._list.id, item.uid, item.summary, version
            )
            _LOGGER.debug(
                "Successfully updated item %s with new name %s", item.uid, item.summary
            )
