"""Helper to deal with YAML + storage."""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from itertools import groupby
import logging
from typing import Any, Awaitable, Callable, Iterable, Optional, cast

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components import websocket_api
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

STORAGE_VERSION = 1
SAVE_DELAY = 10

CHANGE_ADDED = "added"
CHANGE_UPDATED = "updated"
CHANGE_REMOVED = "removed"


@dataclass
class CollectionChangeSet:
    """Class to represent a change set.

    change_type: One of CHANGE_*
    item_id: The id of the item
    item: The item
    """

    change_type: str
    item_id: str
    item: Any


ChangeListener = Callable[
    [
        # Change type
        str,
        # Item ID
        str,
        # New or removed config
        dict,
    ],
    Awaitable[None],
]

ChangeSetListener = Callable[[Iterable[CollectionChangeSet]], Awaitable[None]]


class CollectionError(HomeAssistantError):
    """Base class for collection related errors."""


class ItemNotFound(CollectionError):
    """Raised when an item is not found."""

    def __init__(self, item_id: str) -> None:
        """Initialize item not found error."""
        super().__init__(f"Item {item_id} not found.")
        self.item_id = item_id


class IDManager:
    """Keep track of IDs across different collections."""

    def __init__(self) -> None:
        """Initiate the ID manager."""
        self.collections: list[dict[str, Any]] = []

    def add_collection(self, collection: dict[str, Any]) -> None:
        """Add a collection to check for ID usage."""
        self.collections.append(collection)

    def has_id(self, item_id: str) -> bool:
        """Test if the ID exists."""
        return any(item_id in collection for collection in self.collections)

    def generate_id(self, suggestion: str) -> str:
        """Generate an ID."""
        base = slugify(suggestion)
        proposal = base
        attempt = 1

        while self.has_id(proposal):
            attempt += 1
            proposal = f"{base}_{attempt}"

        return proposal


class ObservableCollection(ABC):
    """Base collection type that can be observed."""

    def __init__(
        self, logger: logging.Logger, id_manager: IDManager | None = None
    ) -> None:
        """Initialize the base collection."""
        self.logger = logger
        self.id_manager = id_manager or IDManager()
        self.data: dict[str, dict] = {}
        self.listeners: list[ChangeListener] = []
        self.change_set_listeners: list[ChangeSetListener] = []

        self.id_manager.add_collection(self.data)

    @callback
    def async_items(self) -> list[dict]:
        """Return list of items in collection."""
        return list(self.data.values())

    @callback
    def async_add_listener(self, listener: ChangeListener) -> None:
        """Add a listener.

        Will be called with (change_type, item_id, updated_config).
        """
        self.listeners.append(listener)

    @callback
    def async_add_change_set_listener(self, listener: ChangeSetListener) -> None:
        """Add a listener for a full change set.

        Will be called with [(change_type, item_id, updated_config), ...]
        """
        self.change_set_listeners.append(listener)

    async def notify_changes(self, change_sets: Iterable[CollectionChangeSet]) -> None:
        """Notify listeners of a change."""
        await asyncio.gather(
            *(
                listener(change_set.change_type, change_set.item_id, change_set.item)
                for listener in self.listeners
                for change_set in change_sets
            ),
            *(
                change_set_listener(change_sets)
                for change_set_listener in self.change_set_listeners
            ),
        )


class YamlCollection(ObservableCollection):
    """Offer a collection based on static data."""

    async def async_load(self, data: list[dict]) -> None:
        """Load the YAML collection. Overrides existing data."""
        old_ids = set(self.data)

        change_sets = []

        for item in data:
            item_id = item[CONF_ID]

            if item_id in old_ids:
                old_ids.remove(item_id)
                event = CHANGE_UPDATED
            elif self.id_manager.has_id(item_id):
                self.logger.warning("Duplicate ID '%s' detected, skipping", item_id)
                continue
            else:
                event = CHANGE_ADDED

            self.data[item_id] = item
            change_sets.append(CollectionChangeSet(event, item_id, item))

        for item_id in old_ids:
            change_sets.append(
                CollectionChangeSet(CHANGE_REMOVED, item_id, self.data.pop(item_id))
            )

        if change_sets:
            await self.notify_changes(change_sets)


class StorageCollection(ObservableCollection):
    """Offer a CRUD interface on top of JSON storage."""

    def __init__(
        self,
        store: Store,
        logger: logging.Logger,
        id_manager: IDManager | None = None,
    ) -> None:
        """Initialize the storage collection."""
        super().__init__(logger, id_manager)
        self.store = store

    @property
    def hass(self) -> HomeAssistant:
        """Home Assistant object."""
        return self.store.hass

    async def _async_load_data(self) -> dict | None:
        """Load the data."""
        return cast(Optional[dict], await self.store.async_load())

    async def async_load(self) -> None:
        """Load the storage Manager."""
        raw_storage = await self._async_load_data()

        if raw_storage is None:
            raw_storage = {"items": []}

        for item in raw_storage["items"]:
            self.data[item[CONF_ID]] = item

        await self.notify_changes(
            [
                CollectionChangeSet(CHANGE_ADDED, item[CONF_ID], item)
                for item in raw_storage["items"]
            ]
        )

    @abstractmethod
    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""

    @callback
    @abstractmethod
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""

    @abstractmethod
    async def _update_data(self, data: dict, update_data: dict) -> dict:
        """Return a new updated data object."""

    async def async_create_item(self, data: dict) -> dict:
        """Create a new item."""
        item = await self._process_create_data(data)
        item[CONF_ID] = self.id_manager.generate_id(self._get_suggested_id(item))
        self.data[item[CONF_ID]] = item
        self._async_schedule_save()
        await self.notify_changes(
            [CollectionChangeSet(CHANGE_ADDED, item[CONF_ID], item)]
        )
        return item

    async def async_update_item(self, item_id: str, updates: dict) -> dict:
        """Update item."""
        if item_id not in self.data:
            raise ItemNotFound(item_id)

        if CONF_ID in updates:
            raise ValueError("Cannot update ID")

        current = self.data[item_id]

        updated = await self._update_data(current, updates)

        self.data[item_id] = updated
        self._async_schedule_save()

        await self.notify_changes(
            [CollectionChangeSet(CHANGE_UPDATED, item_id, updated)]
        )

        return self.data[item_id]

    async def async_delete_item(self, item_id: str) -> None:
        """Delete item."""
        if item_id not in self.data:
            raise ItemNotFound(item_id)

        item = self.data.pop(item_id)
        self._async_schedule_save()

        await self.notify_changes([CollectionChangeSet(CHANGE_REMOVED, item_id, item)])

    @callback
    def _async_schedule_save(self) -> None:
        """Schedule saving the area registry."""
        self.store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict:
        """Return data of area registry to store in a file."""
        return {"items": list(self.data.values())}


class IDLessCollection(ObservableCollection):
    """A collection without IDs."""

    counter = 0

    async def async_load(self, data: list[dict]) -> None:
        """Load the collection. Overrides existing data."""
        await self.notify_changes(
            [
                CollectionChangeSet(CHANGE_REMOVED, item_id, item)
                for item_id, item in list(self.data.items())
            ]
        )

        self.data.clear()

        for item in data:
            self.counter += 1
            item_id = f"fakeid-{self.counter}"

            self.data[item_id] = item

        await self.notify_changes(
            [
                CollectionChangeSet(CHANGE_ADDED, item_id, item)
                for item_id, item in self.data.items()
            ]
        )


@callback
def sync_entity_lifecycle(
    hass: HomeAssistant,
    domain: str,
    platform: str,
    entity_component: EntityComponent,
    collection: ObservableCollection,
    create_entity: Callable[[dict], Entity],
) -> None:
    """Map a collection to an entity component."""
    entities = {}
    ent_reg = entity_registry.async_get(hass)

    async def _add_entity(change_set: CollectionChangeSet) -> Entity:
        entities[change_set.item_id] = create_entity(change_set.item)
        return entities[change_set.item_id]

    async def _remove_entity(change_set: CollectionChangeSet) -> None:
        ent_to_remove = ent_reg.async_get_entity_id(
            domain, platform, change_set.item_id
        )
        if ent_to_remove is not None:
            ent_reg.async_remove(ent_to_remove)
        else:
            await entities[change_set.item_id].async_remove(force_remove=True)
        entities.pop(change_set.item_id)

    async def _update_entity(change_set: CollectionChangeSet) -> None:
        await entities[change_set.item_id].async_update_config(change_set.item)  # type: ignore

    _func_map: dict[
        str, Callable[[CollectionChangeSet], Coroutine[Any, Any, Entity | None]]
    ] = {
        CHANGE_ADDED: _add_entity,
        CHANGE_REMOVED: _remove_entity,
        CHANGE_UPDATED: _update_entity,
    }

    async def _collection_changed(change_sets: Iterable[CollectionChangeSet]) -> None:
        """Handle a collection change."""
        # Create a new bucket every time we have a different change type
        # to ensure operations happen in order. We only group
        # the same change type.
        for _, grouped in groupby(
            change_sets, lambda change_set: change_set.change_type
        ):
            new_entities = [
                entity
                for entity in await asyncio.gather(
                    *(
                        _func_map[change_set.change_type](change_set)
                        for change_set in grouped
                    )
                )
                if entity is not None
            ]
            if new_entities:
                await entity_component.async_add_entities(new_entities)

    collection.async_add_change_set_listener(_collection_changed)


class StorageCollectionWebsocket:
    """Class to expose storage collection management over websocket."""

    def __init__(
        self,
        storage_collection: StorageCollection,
        api_prefix: str,
        model_name: str,
        create_schema: dict,
        update_schema: dict,
    ) -> None:
        """Initialize a websocket CRUD."""
        self.storage_collection = storage_collection
        self.api_prefix = api_prefix
        self.model_name = model_name
        self.create_schema = create_schema
        self.update_schema = update_schema

        assert self.api_prefix[-1] != "/", "API prefix should not end in /"

    @property
    def item_id_key(self) -> str:
        """Return item ID key."""
        return f"{self.model_name}_id"

    @callback
    def async_setup(
        self,
        hass: HomeAssistant,
        *,
        create_list: bool = True,
        create_create: bool = True,
    ) -> None:
        """Set up the websocket commands."""
        if create_list:
            websocket_api.async_register_command(
                hass,
                f"{self.api_prefix}/list",
                self.ws_list_item,
                websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
                    {vol.Required("type"): f"{self.api_prefix}/list"}
                ),
            )

        if create_create:
            websocket_api.async_register_command(
                hass,
                f"{self.api_prefix}/create",
                websocket_api.require_admin(
                    websocket_api.async_response(self.ws_create_item)
                ),
                websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
                    {
                        **self.create_schema,
                        vol.Required("type"): f"{self.api_prefix}/create",
                    }
                ),
            )

        websocket_api.async_register_command(
            hass,
            f"{self.api_prefix}/update",
            websocket_api.require_admin(
                websocket_api.async_response(self.ws_update_item)
            ),
            websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
                {
                    **self.update_schema,
                    vol.Required("type"): f"{self.api_prefix}/update",
                    vol.Required(self.item_id_key): str,
                }
            ),
        )

        websocket_api.async_register_command(
            hass,
            f"{self.api_prefix}/delete",
            websocket_api.require_admin(
                websocket_api.async_response(self.ws_delete_item)
            ),
            websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
                {
                    vol.Required("type"): f"{self.api_prefix}/delete",
                    vol.Required(self.item_id_key): str,
                }
            ),
        )

    def ws_list_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """List items."""
        connection.send_result(msg["id"], self.storage_collection.async_items())

    async def ws_create_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Create a item."""
        try:
            data = dict(msg)
            data.pop("id")
            data.pop("type")
            item = await self.storage_collection.async_create_item(data)
            connection.send_result(msg["id"], item)
        except vol.Invalid as err:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_INVALID_FORMAT,
                humanize_error(data, err),
            )
        except ValueError as err:
            connection.send_error(
                msg["id"], websocket_api.const.ERR_INVALID_FORMAT, str(err)
            )

    async def ws_update_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Update a item."""
        data = dict(msg)
        msg_id = data.pop("id")
        item_id = data.pop(self.item_id_key)
        data.pop("type")

        try:
            item = await self.storage_collection.async_update_item(item_id, data)
            connection.send_result(msg_id, item)
        except ItemNotFound:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_NOT_FOUND,
                f"Unable to find {self.item_id_key} {item_id}",
            )
        except vol.Invalid as err:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_INVALID_FORMAT,
                humanize_error(data, err),
            )
        except ValueError as err:
            connection.send_error(
                msg_id, websocket_api.const.ERR_INVALID_FORMAT, str(err)
            )

    async def ws_delete_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Delete a item."""
        try:
            await self.storage_collection.async_delete_item(msg[self.item_id_key])
        except ItemNotFound:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_NOT_FOUND,
                f"Unable to find {self.item_id_key} {msg[self.item_id_key]}",
            )

        connection.send_result(msg["id"])
