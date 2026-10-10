"""Todo platform for AnyList."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol, cast, override

from aioanylist import AnyListError

from homeassistant.components.todo import (
    DOMAIN as TODO_DOMAIN,
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnyListConfigEntry, AnyListDataUpdateCoordinator

PARALLEL_UPDATES = 0


class _AnyListItem(Protocol):
    """Fields used from an AnyList protobuf list item."""

    @property
    def identifier(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def checked(self) -> bool: ...

    @property
    def details(self) -> str: ...


class _AnyListShoppingList(Protocol):
    """Fields used from an AnyList protobuf shopping list."""

    @property
    def name(self) -> str: ...

    @property
    def items(self) -> Iterable[_AnyListItem]: ...


def _convert_item(item: _AnyListItem) -> TodoItem:
    """Convert an AnyList item to a Home Assistant todo item."""
    return TodoItem(
        uid=str(item.identifier),
        summary=str(item.name),
        status=(
            TodoItemStatus.COMPLETED if item.checked else TodoItemStatus.NEEDS_ACTION
        ),
        description=str(item.details) or None,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnyListConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AnyList todo entities."""
    coordinator = entry.runtime_data
    added_lists: set[str] = set()
    account_id = cast(str, entry.unique_id)
    entity_registry = er.async_get(hass)

    current_lists = set(coordinator.data.shopping_lists)
    unique_id_prefix = f"{account_id}_"
    for registry_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if (
            registry_entry.domain == TODO_DOMAIN
            and registry_entry.platform == DOMAIN
            and registry_entry.unique_id.startswith(unique_id_prefix)
            and registry_entry.unique_id.removeprefix(unique_id_prefix)
            not in current_lists
        ):
            entity_registry.async_remove(registry_entry.entity_id)

    @callback
    def async_update_entities() -> None:
        """Add and remove entities as AnyList shopping lists change."""
        current_lists = set(coordinator.data.shopping_lists)
        new_lists = current_lists - added_lists
        removed_lists = added_lists - current_lists

        if new_lists:
            async_add_entities(
                AnyListTodoListEntity(coordinator, account_id, list_id)
                for list_id in new_lists
            )
            added_lists.update(new_lists)

        if removed_lists:
            for list_id in removed_lists:
                if entity_id := entity_registry.async_get_entity_id(
                    TODO_DOMAIN,
                    DOMAIN,
                    f"{account_id}_{list_id}",
                ):
                    entity_registry.async_remove(entity_id)
            added_lists.difference_update(removed_lists)

    entry.async_on_unload(coordinator.async_add_listener(async_update_entities))
    async_update_entities()


class AnyListTodoListEntity(
    CoordinatorEntity[AnyListDataUpdateCoordinator], TodoListEntity
):
    """Representation of an AnyList shopping list."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(
        self,
        coordinator: AnyListDataUpdateCoordinator,
        account_id: str,
        list_id: str,
    ) -> None:
        """Initialize an AnyList todo entity."""
        super().__init__(coordinator)
        self._list_id = list_id
        self._attr_unique_id = f"{account_id}_{list_id}"
        self._attr_name = self.shopping_list.name

    @property
    def shopping_list(self) -> _AnyListShoppingList:
        """Return the backing AnyList shopping list."""
        return self.coordinator.data.shopping_lists[self._list_id]

    @property
    @override
    def todo_items(self) -> list[TodoItem]:
        """Return items in the shopping list."""
        if (
            shopping_list := self.coordinator.data.shopping_lists.get(self._list_id)
        ) is None:
            return []
        return [_convert_item(item) for item in shopping_list.items]

    @property
    @override
    def available(self) -> bool:
        """Return whether the shopping list still exists."""
        return (
            super().available and self._list_id in self.coordinator.data.shopping_lists
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle an updated shopping list."""
        if self._list_id in self.coordinator.data.shopping_lists:
            self._attr_name = self.shopping_list.name
        super()._handle_coordinator_update()

    @override
    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the shopping list."""
        lists = self.coordinator.client.lists
        if TYPE_CHECKING:
            assert lists is not None
        try:
            await lists.add_item(
                self._list_id,
                item.summary or "",
                details=item.description,
            )
        except (AnyListError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="add_item_failed",
                translation_placeholders={"list_name": self.shopping_list.name},
            ) from err
        self.coordinator.async_update_from_client()

    @override
    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item in the shopping list."""
        lists = self.coordinator.client.lists
        if TYPE_CHECKING:
            assert lists is not None
        uid = cast(str, item.uid)
        current = lists.item(self._list_id, uid)
        if TYPE_CHECKING:
            assert current is not None

        try:
            if item.summary is not None and item.summary != current.name:
                await lists.rename_item(self._list_id, uid, item.summary, flush=False)

            checked = item.status == TodoItemStatus.COMPLETED
            if item.status is not None and checked != bool(current.checked):
                await lists.set_checked(self._list_id, uid, checked, flush=False)

            details = item.description or ""
            if details != str(current.details):
                await lists.set_details(self._list_id, uid, details, flush=False)

            await self.coordinator.client.flush()
        except (AnyListError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_item_failed",
                translation_placeholders={"list_name": self.shopping_list.name},
            ) from err
        self.coordinator.async_update_from_client()

    @override
    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete items from the shopping list."""
        lists = self.coordinator.client.lists
        if TYPE_CHECKING:
            assert lists is not None
        try:
            await lists.bulk_remove_items(self._list_id, uids)
        except (AnyListError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="delete_item_failed",
                translation_placeholders={"list_name": self.shopping_list.name},
            ) from err
        self.coordinator.async_update_from_client()
