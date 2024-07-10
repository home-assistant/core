"""Helper to deal with YAML + storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterable
from dataclasses import dataclass
from functools import partial
from itertools import groupby
import logging
from operator import attrgetter
from typing import Any, Generic, TypedDict

from typing_extensions import TypeVar
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components import websocket_api
from homeassistant.const import CONF_ID
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from . import entity_registry
from .entity import Entity
from .entity_component import EntityComponent
from .storage import Store
from .typing import ConfigType, VolDictType

STORAGE_VERSION = 1
SAVE_DELAY = 10

CHANGE_ADDED = "added"
CHANGE_UPDATED = "updated"
CHANGE_REMOVED = "removed"

_EntityT = TypeVar("_EntityT", bound=Entity, default=Entity)


@dataclass(slots=True)
class CollectionChange:
    """Class to represent an item in a change set.

    change_type: One of CHANGE_*
    item_id: The id of the item
    item: The item
    """

    change_type: str
    item_id: str
    item: Any


type ChangeListener = Callable[
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

type ChangeSetListener = Callable[[Iterable[CollectionChange]], Awaitable[None]]


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


class CollectionEntity(Entity):
    """Mixin class for entities managed by an ObservableCollection."""

    @classmethod
    @abstractmethod
    def from_storage(cls, config: ConfigType) -> CollectionEntity:
        """Create instance from storage."""

    @classmethod
    @abstractmethod
    def from_yaml(cls, config: ConfigType) -> CollectionEntity:
        """Create instance from yaml config."""

    @abstractmethod
    async def async_update_config(self, config: ConfigType) -> None:
        """Handle updated configuration."""


class ObservableCollection[_ItemT](ABC):
    """Base collection type that can be observed."""

    def __init__(self, id_manager: IDManager | None) -> None:
        """Initialize the base collection."""
        self.id_manager = id_manager or IDManager()
        self.data: dict[str, _ItemT] = {}
        self.listeners: list[ChangeListener] = []
        self.change_set_listeners: list[ChangeSetListener] = []

        self.id_manager.add_collection(self.data)

    @callback
    def async_items(self) -> list[_ItemT]:
        """Return list of items in collection."""
        return list(self.data.values())

    @callback
    def async_add_listener(self, listener: ChangeListener) -> Callable[[], None]:
        """Add a listener.

        Will be called with (change_type, item_id, updated_config).
        """
        self.listeners.append(listener)
        return partial(self.listeners.remove, listener)

    @callback
    def async_add_change_set_listener(
        self, listener: ChangeSetListener
    ) -> Callable[[], None]:
        """Add a listener for a full change set.

        Will be called with [(change_type, item_id, updated_config), ...]
        """
        self.change_set_listeners.append(listener)
        return partial(self.change_set_listeners.remove, listener)

    async def notify_changes(self, change_set: Iterable[CollectionChange]) -> None:
        """Notify listeners of a change."""
        await asyncio.gather(
            *(
                listener(change.change_type, change.item_id, change.item)
                for listener in self.listeners
                for change in change_set
            ),
            *(
                change_set_listener(change_set)
                for change_set_listener in self.change_set_listeners
            ),
        )


class YamlCollection(ObservableCollection[dict]):
    """Offer a collection based on static data."""

    def __init__(
        self,
        logger: logging.Logger,
        id_manager: IDManager | None = None,
    ) -> None:
        """Initialize the storage collection."""
        super().__init__(id_manager)
        self.logger = logger

    @staticmethod
    def create_entity(
        entity_class: type[CollectionEntity], config: ConfigType
    ) -> CollectionEntity:
        """Create a CollectionEntity instance."""
        return entity_class.from_yaml(config)

    async def async_load(self, data: list[dict]) -> None:
        """Load the YAML collection. Overrides existing data."""
        old_ids = set(self.data)

        change_set = []

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
            change_set.append(CollectionChange(event, item_id, item))

        change_set.extend(
            CollectionChange(CHANGE_REMOVED, item_id, self.data.pop(item_id))
            for item_id in old_ids
        )

        if change_set:
            await self.notify_changes(change_set)


class SerializedStorageCollection(TypedDict):
    """Serialized storage collection."""

    items: list[dict[str, Any]]


class StorageCollection[_ItemT, _StoreT: SerializedStorageCollection](
    ObservableCollection[_ItemT]
):
    """Offer a CRUD interface on top of JSON storage."""

    def __init__(
        self,
        store: Store[_StoreT],
        id_manager: IDManager | None = None,
    ) -> None:
        """Initialize the storage collection."""
        super().__init__(id_manager)
        self.store = store

    @staticmethod
    def create_entity(
        entity_class: type[CollectionEntity], config: ConfigType
    ) -> CollectionEntity:
        """Create a CollectionEntity instance."""
        return entity_class.from_storage(config)

    @property
    def hass(self) -> HomeAssistant:
        """Home Assistant object."""
        return self.store.hass

    async def _async_load_data(self) -> _StoreT | None:
        """Load the data."""
        return await self.store.async_load()

    async def async_load(self) -> None:
        """Load the storage Manager."""
        if not (raw_storage := await self._async_load_data()):
            return

        for item in raw_storage["items"]:
            self.data[item[CONF_ID]] = self._deserialize_item(item)

        await self.notify_changes(
            [
                CollectionChange(CHANGE_ADDED, item[CONF_ID], item)
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
    async def _update_data(self, item: _ItemT, update_data: dict) -> _ItemT:
        """Return a new updated item."""

    @abstractmethod
    def _create_item(self, item_id: str, data: dict) -> _ItemT:
        """Create an item from validated config."""

    @abstractmethod
    def _deserialize_item(self, data: dict) -> _ItemT:
        """Create an item from its serialized representation."""

    @abstractmethod
    def _serialize_item(self, item_id: str, item: _ItemT) -> dict:
        """Return the serialized representation of an item for storing.

        The serialized representation must include the item_id in the "id" key.
        """

    async def async_create_item(self, data: dict) -> _ItemT:
        """Create a new item."""
        validated_data = await self._process_create_data(data)
        item_id = self.id_manager.generate_id(self._get_suggested_id(validated_data))
        item = self._create_item(item_id, validated_data)
        self.data[item_id] = item
        self._async_schedule_save()
        await self.notify_changes([CollectionChange(CHANGE_ADDED, item_id, item)])
        return item

    async def async_update_item(self, item_id: str, updates: dict) -> _ItemT:
        """Update item."""
        if item_id not in self.data:
            raise ItemNotFound(item_id)

        if CONF_ID in updates:
            raise ValueError("Cannot update ID")

        current = self.data[item_id]

        updated = await self._update_data(current, updates)

        self.data[item_id] = updated
        self._async_schedule_save()

        await self.notify_changes([CollectionChange(CHANGE_UPDATED, item_id, updated)])

        return self.data[item_id]

    async def async_delete_item(self, item_id: str) -> None:
        """Delete item."""
        if item_id not in self.data:
            raise ItemNotFound(item_id)

        item = self.data.pop(item_id)
        self._async_schedule_save()

        await self.notify_changes([CollectionChange(CHANGE_REMOVED, item_id, item)])

    @callback
    def _async_schedule_save(self) -> None:
        """Schedule saving the collection."""
        self.store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _base_data_to_save(self) -> SerializedStorageCollection:
        """Return JSON-compatible data for storing to file."""
        return {
            "items": [
                self._serialize_item(item_id, item)
                for item_id, item in self.data.items()
            ]
        }

    @abstractmethod
    @callback
    def _data_to_save(self) -> _StoreT:
        """Return JSON-compatible date for storing to file."""


class DictStorageCollection(StorageCollection[dict, SerializedStorageCollection]):
    """A specialized StorageCollection where the items are untyped dicts."""

    def _create_item(self, item_id: str, data: dict) -> dict:
        """Create an item from its validated, serialized representation."""
        return {CONF_ID: item_id} | data

    def _deserialize_item(self, data: dict) -> dict:
        """Create an item from its validated, serialized representation."""
        return data

    def _serialize_item(self, item_id: str, item: dict) -> dict:
        """Return the serialized representation of an item for storing."""
        return item

    @callback
    def _data_to_save(self) -> SerializedStorageCollection:
        """Return JSON-compatible date for storing to file."""
        return self._base_data_to_save()


class IDLessCollection(YamlCollection):
    """A collection without IDs."""

    counter = 0

    async def async_load(self, data: list[dict]) -> None:
        """Load the collection. Overrides existing data."""
        await self.notify_changes(
            [
                CollectionChange(CHANGE_REMOVED, item_id, item)
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
                CollectionChange(CHANGE_ADDED, item_id, item)
                for item_id, item in self.data.items()
            ]
        )


_GROUP_BY_KEY = attrgetter("change_type")


@dataclass(slots=True, frozen=True)
class _CollectionLifeCycle(Generic[_EntityT]):
    """Life cycle for a collection of entities."""

    domain: str
    platform: str
    entity_component: EntityComponent[_EntityT]
    collection: StorageCollection | YamlCollection
    entity_class: type[CollectionEntity]
    ent_reg: entity_registry.EntityRegistry
    entities: dict[str, CollectionEntity]

    @callback
    def async_setup(self) -> None:
        """Set up the collection life cycle."""
        self.collection.async_add_change_set_listener(self._collection_changed)

    def _entity_removed(self, item_id: str) -> None:
        """Remove entity from entities if it's removed or not added."""
        self.entities.pop(item_id, None)

    @callback
    def _add_entity(self, change_set: CollectionChange) -> CollectionEntity:
        item_id = change_set.item_id
        entity = self.collection.create_entity(self.entity_class, change_set.item)
        self.entities[item_id] = entity
        entity.async_on_remove(partial(self._entity_removed, item_id))
        return entity

    async def _remove_entity(self, change_set: CollectionChange) -> None:
        item_id = change_set.item_id
        ent_reg = self.ent_reg
        entities = self.entities
        ent_to_remove = ent_reg.async_get_entity_id(self.domain, self.platform, item_id)
        if ent_to_remove is not None:
            ent_reg.async_remove(ent_to_remove)
        elif entity := entities.get(item_id):
            await entity.async_remove(force_remove=True)
        # Unconditionally pop the entity from the entity list to avoid racing against
        # the entity registry event handled by Entity._async_registry_updated
        entities.pop(item_id, None)

    async def _update_entity(self, change_set: CollectionChange) -> None:
        if entity := self.entities.get(change_set.item_id):
            await entity.async_update_config(change_set.item)

    async def _collection_changed(self, change_set: Iterable[CollectionChange]) -> None:
        """Handle a collection change."""
        # Create a new bucket every time we have a different change type
        # to ensure operations happen in order. We only group
        # the same change type.
        new_entities: list[CollectionEntity] = []
        coros: list[Coroutine[Any, Any, CollectionEntity | None]] = []
        grouped: Iterable[CollectionChange]
        for _, grouped in groupby(change_set, _GROUP_BY_KEY):
            for change in grouped:
                change_type = change.change_type
                if change_type == CHANGE_ADDED:
                    new_entities.append(self._add_entity(change))
                elif change_type == CHANGE_REMOVED:
                    coros.append(self._remove_entity(change))
                elif change_type == CHANGE_UPDATED:
                    coros.append(self._update_entity(change))

        if coros:
            await asyncio.gather(*coros)

        if new_entities:
            await self.entity_component.async_add_entities(new_entities)


@callback
def sync_entity_lifecycle(
    hass: HomeAssistant,
    domain: str,
    platform: str,
    entity_component: EntityComponent[_EntityT],
    collection: StorageCollection | YamlCollection,
    entity_class: type[CollectionEntity],
) -> None:
    """Map a collection to an entity component."""
    ent_reg = entity_registry.async_get(hass)
    _CollectionLifeCycle(
        domain, platform, entity_component, collection, entity_class, ent_reg, {}
    ).async_setup()


class StorageCollectionWebsocket[_StorageCollectionT: StorageCollection]:
    """Class to expose storage collection management over websocket."""

    def __init__(
        self,
        storage_collection: _StorageCollectionT,
        api_prefix: str,
        model_name: str,
        create_schema: VolDictType,
        update_schema: VolDictType,
    ) -> None:
        """Initialize a websocket CRUD."""
        self.storage_collection = storage_collection
        self.api_prefix = api_prefix
        self.model_name = model_name
        self.create_schema = create_schema
        self.update_schema = update_schema

        self._remove_subscription: CALLBACK_TYPE | None = None
        self._subscribers: set[tuple[websocket_api.ActiveConnection, int]] = set()

        assert self.api_prefix[-1] != "/", "API prefix should not end in /"

    @property
    def item_id_key(self) -> str:
        """Return item ID key."""
        return f"{self.model_name}_id"

    @callback
    def async_setup(self, hass: HomeAssistant) -> None:
        """Set up the websocket commands."""
        websocket_api.async_register_command(
            hass,
            f"{self.api_prefix}/list",
            self.ws_list_item,
            websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
                {vol.Required("type"): f"{self.api_prefix}/list"}
            ),
        )

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
            f"{self.api_prefix}/subscribe",
            self._ws_subscribe,
            websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
                {vol.Required("type"): f"{self.api_prefix}/subscribe"}
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

    @callback
    def ws_list_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """List items."""
        connection.send_result(msg["id"], self.storage_collection.async_items())

    async def ws_create_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Create an item."""
        try:
            data = dict(msg)
            data.pop("id")
            data.pop("type")
            item = await self.storage_collection.async_create_item(data)
            connection.send_result(msg["id"], item)
        except vol.Invalid as err:
            connection.send_error(
                msg["id"],
                websocket_api.ERR_INVALID_FORMAT,
                humanize_error(data, err),
            )
        except ValueError as err:
            connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))

    @callback
    def _ws_subscribe(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Subscribe to collection updates."""

        async def async_change_listener(
            change_set: Iterable[CollectionChange],
        ) -> None:
            json_msg = [
                {
                    "change_type": change.change_type,
                    self.item_id_key: change.item_id,
                    "item": change.item,
                }
                for change in change_set
            ]
            for conn, msg_id in self._subscribers:
                conn.send_message(websocket_api.event_message(msg_id, json_msg))

        if not self._subscribers:
            self._remove_subscription = (
                self.storage_collection.async_add_change_set_listener(
                    async_change_listener
                )
            )

        self._subscribers.add((connection, msg["id"]))

        @callback
        def cancel_subscription() -> None:
            self._subscribers.remove((connection, msg["id"]))
            if not self._subscribers and self._remove_subscription:
                self._remove_subscription()
                self._remove_subscription = None

        connection.subscriptions[msg["id"]] = cancel_subscription

        connection.send_message(websocket_api.result_message(msg["id"]))

        json_msg = [
            {
                "change_type": CHANGE_ADDED,
                self.item_id_key: item_id,
                "item": item,
            }
            for item_id, item in self.storage_collection.data.items()
        ]
        connection.send_message(websocket_api.event_message(msg["id"], json_msg))

    async def ws_update_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Update an item."""
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
                websocket_api.ERR_NOT_FOUND,
                f"Unable to find {self.item_id_key} {item_id}",
            )
        except vol.Invalid as err:
            connection.send_error(
                msg["id"],
                websocket_api.ERR_INVALID_FORMAT,
                humanize_error(data, err),
            )
        except ValueError as err:
            connection.send_error(msg_id, websocket_api.ERR_INVALID_FORMAT, str(err))

    async def ws_delete_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Delete an item."""
        try:
            await self.storage_collection.async_delete_item(msg[self.item_id_key])
        except ItemNotFound:
            connection.send_error(
                msg["id"],
                websocket_api.ERR_NOT_FOUND,
                f"Unable to find {self.item_id_key} {msg[self.item_id_key]}",
            )

        connection.send_result(msg["id"])


class DictStorageCollectionWebsocket(StorageCollectionWebsocket[DictStorageCollection]):
    """Class to expose storage collection management over websocket."""
