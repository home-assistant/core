"""Platform for Alexa To-do integration."""

from typing import TYPE_CHECKING

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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import EntityDescription

from .const import _LOGGER, DOMAIN
from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator
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
    """Representation of an Alexa To-do List."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(
        self, coordinator: AmazonDevicesCoordinator, alexa_list: AmazonListInfo
    ) -> None:
        """Initialize an AlexaTodoList."""
        self._coordinator = coordinator
        self._list = alexa_list

        if alexa_list.list_type == AmazonListType.CUSTOM:
            # Custom list -> Use actual name
            entity_description = EntityDescription(
                key=alexa_list.id, name=alexa_list.name
            )
        else:
            entity_description = EntityDescription(
                key=alexa_list.id, translation_key=alexa_list.list_type.lower()
            )

        self._attr_unique_id = alexa_list.id

        super().__init__(coordinator, entity_description)

        _LOGGER.debug(
            "Created todo entity for list: %s (ID: %s)", self._list.name, self._list.id
        )

    @property
    def todo_items(self) -> list[TodoItem]:
        """All Todo items in the list."""

        todo_items = self._coordinator.todo_list_items.get(self._list.id, {}).values()

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

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        _LOGGER.debug(
            "Creating todo item: %s for list: %s", item.summary, self._list.name
        )

        if not item.summary:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="todo_item_summary_empty",
            )

        await self._coordinator.api.add_todo_list_item(self._list.id, item.summary)

        _LOGGER.debug(
            "Successfully created todo item: %s for list: %s",
            item.summary,
            self._list.name,
        )

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete items from the to-do list."""
        _LOGGER.debug("Called async_delete_todo_items for %s item(s)", len(uids))

        list_items_lookup = self._coordinator.todo_list_items.get(self._list.id)

        if list_items_lookup is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="todo_items_lookup_not_found",
                translation_placeholders={"entity_id": self.entity_id},
            )

        for uid in uids:
            existing_item = list_items_lookup.get(uid)

            if existing_item is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="todo_item_not_found",
                    translation_placeholders={
                        "uid": uid,
                        "entity_id": self.entity_id,
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
        """Update an item in the To-do list."""
        if not item.summary or not item.uid:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="todo_item_summary_uid_required",
            )

        list_items_lookup = self._coordinator.todo_list_items.get(self._list.id)

        if list_items_lookup is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="todo_items_lookup_not_found",
                translation_placeholders={"entity_id": self.entity_id},
            )

        existing_item = list_items_lookup.get(item.uid)

        if existing_item is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="todo_item_not_found",
                translation_placeholders={
                    "uid": item.uid,
                    "entity_id": self.entity_id,
                },
            )

        # Check what has changed
        has_completed_changed = (
            existing_item.status == AmazonListItemStatus.COMPLETE
        ) != (item.status == TodoItemStatus.COMPLETED)
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
