"""Platform for Alexa To-do integration."""

import logging
from typing import TYPE_CHECKING

from aioamazondevices.implementation.todo import is_item_complete
from aioamazondevices.structures import ListType

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import EntityDescription

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

        # To be always unique because multiple Amazon
        # accounts can have lists with same names
        self._attr_unique_id = alexa_list.id
        self._attr_name = alexa_list.name

        super().__init__(
            coordinator,
            EntityDescription(key=alexa_list.id, name=alexa_list.name),
        )

        _LOGGER.debug(
            "Created todo entity for list: %s (ID: %s)", self._list.name, self._list.id
        )

    @property
    def icon(self) -> str | None:
        """Return the icon to use for this entity.

        Returns:
            The icon to use for this entity.

        """
        if self._list.list_type == ListType.SHOP:
            return "mdi:cart"
        return "mdi:clipboard-list"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """All Todo items in the list.

        Returns:
            List of TodoItems in the list.
        """
        todo_items: list[ListItem] | None = self._coordinator.api.todo_list_items.get(
            self._list.id
        )

        if not todo_items:
            return None

        return [
            TodoItem(
                uid=item.id,
                summary=item.name.capitalize(),
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
            raise ServiceValidationError("Item summary cannot be empty.")

        await self._coordinator.api.add_todo_list_item(self._list.id, item.summary)

        _LOGGER.debug(
            "Successfully created todo item: %s for list: %s",
            item.summary,
            self._list.name,
        )

        # Update the list (important to get new version number)
        await self._coordinator.api.update_todo_list_items(list_id=self._list.id)
        self.async_write_ha_state()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete items from the to-do list.

        Args:
            uids: The unique IDs of the items to delete.

        """
        _LOGGER.debug("Called async_delete_todo_items for %s item(s)", len(uids))

        for uid in uids:
            existing_item = self._coordinator.api.todo_list_items_lookup[self._list.id][
                uid
            ]
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
        await self._coordinator.api.update_todo_list_items(list_id=self._list.id)
        self.async_write_ha_state()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item in the To-do list.

        Args:
            item: The item to update.

        Raises:
            ServiceValidationError: If the item summary or UID is missing.

        """
        if not item.summary or not item.uid:
            raise ServiceValidationError("Item summary and UID are required.")

        existing_item = self._coordinator.api.todo_list_items_lookup[self._list.id][
            item.uid
        ]

        updated = False

        if is_item_complete(existing_item) != (item.status == TodoItemStatus.COMPLETED):
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
            updated = True
            _LOGGER.debug(
                "Successfully updated item %s with checked status %s",
                item.uid,
                item.status,
            )
        elif existing_item.name != item.summary:
            # Name has changed, update it
            _LOGGER.debug("Updating item %s with new name %s", item.uid, item.summary)
            await self._coordinator.api.rename_todo_list_item(
                self._list.id, item.uid, item.summary, existing_item.version
            )
            updated = True
            _LOGGER.debug(
                "Successfully updated item %s with new name %s", item.uid, item.summary
            )

        if updated:
            # Update the list (important to get new version number)
            await self._coordinator.api.update_todo_list_items(list_id=self._list.id)
            self.async_write_ha_state()
