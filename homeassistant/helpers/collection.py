"""Helper to deal with YAML + storage."""
from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast

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
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import slugify

STORAGE_VERSION = 1
SAVE_DELAY = 10

CHANGE_ADDED = "added"
CHANGE_UPDATED = "updated"
CHANGE_REMOVED = "removed"


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


class CollectionError(HomeAssistantError):
    """Base class for collection related errors."""


class ItemNotFound(CollectionError):
    """Raised when an item is not found."""

    def __init__(self, item_id: str):
        """Initialize item not found error."""
        super().__init__(f"Item {item_id} not found.")
        self.item_id = item_id


class IDManager:
    """Keep track of IDs across different collections."""

    def __init__(self) -> None:
        """Initiate the ID manager."""
        self.collections: List[Dict[str, Any]] = []

    def add_collection(self, collection: Dict[str, Any]) -> None:
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

    def __init__(self, logger: logging.Logger, id_manager: Optional[IDManager] = None):
        """Initialize the base collection."""
        self.logger = logger
        self.id_manager = id_manager or IDManager()
        self.data: Dict[str, dict] = {}
        self.listeners: List[ChangeListener] = []

        self.id_manager.add_collection(self.data)

    @callback
    def async_items(self) -> List[dict]:
        """Return list of items in collection."""
        return list(self.data.values())

    @callback
    def async_add_listener(self, listener: ChangeListener) -> None:
        """Add a listener.

        Will be called with (change_type, item_id, updated_config).
        """
        self.listeners.append(listener)

    async def notify_change(self, change_type: str, item_id: str, item: dict) -> None:
        """Notify listeners of a change."""
        self.logger.debug("%s %s: %s", change_type, item_id, item)
        await asyncio.gather(
            *[listener(change_type, item_id, item) for listener in self.listeners]
        )


class YamlCollection(ObservableCollection):
    """Offer a collection based on static data."""

    async def async_load(self, data: List[dict]) -> None:
        """Load the YAML collection. Overrides existing data."""
        old_ids = set(self.data)

        tasks = []

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
            tasks.append(self.notify_change(event, item_id, item))

        for item_id in old_ids:
            tasks.append(
                self.notify_change(CHANGE_REMOVED, item_id, self.data.pop(item_id))
            )

        if tasks:
            await asyncio.gather(*tasks)


class StorageCollection(ObservableCollection):
    """Offer a CRUD interface on top of JSON storage."""

    def __init__(
        self,
        store: Store,
        logger: logging.Logger,
        id_manager: Optional[IDManager] = None,
    ):
        """Initialize the storage collection."""
        super().__init__(logger, id_manager)
        self.store = store

    @property
    def hass(self) -> HomeAssistant:
        """Home Assistant object."""
        return self.store.hass

    async def _async_load_data(self) -> Optional[dict]:
        """Load the data."""
        return cast(Optional[dict], await self.store.async_load())

    async def async_load(self) -> None:
        """Load the storage Manager."""
        raw_storage = await self._async_load_data()

        if raw_storage is None:
            raw_storage = {"items": []}

        for item in raw_storage["items"]:
            self.data[item[CONF_ID]] = item

        await asyncio.gather(
            *[
                self.notify_change(CHANGE_ADDED, item[CONF_ID], item)
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
        await self.notify_change(CHANGE_ADDED, item[CONF_ID], item)
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

        await self.notify_change(CHANGE_UPDATED, item_id, updated)

        return self.data[item_id]

    async def async_delete_item(self, item_id: str) -> None:
        """Delete item."""
        if item_id not in self.data:
            raise ItemNotFound(item_id)

        item = self.data.pop(item_id)
        self._async_schedule_save()

        await self.notify_change(CHANGE_REMOVED, item_id, item)

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

    async def async_load(self, data: List[dict]) -> None:
        """Load the collection. Overrides existing data."""
        await asyncio.gather(
            *[
                self.notify_change(CHANGE_REMOVED, item_id, item)
                for item_id, item in list(self.data.items())
            ]
        )

        self.data.clear()

        for item in data:
            self.counter += 1
            item_id = f"fakeid-{self.counter}"

            self.data[item_id] = item

        await asyncio.gather(
            *[
                self.notify_change(CHANGE_ADDED, item_id, item)
                for item_id, item in self.data.items()
            ]
        )


@callback
def attach_entity_component_collection(
    entity_component: EntityComponent,
    collection: ObservableCollection,
    create_entity: Callable[[dict], Entity],
) -> None:
    """Map a collection to an entity component."""
    entities = {}

    async def _collection_changed(change_type: str, item_id: str, config: dict) -> None:
        """Handle a collection change."""
        if change_type == CHANGE_ADDED:
            entity = create_entity(config)
            await entity_component.async_add_entities([entity])
            entities[item_id] = entity
            return

        if change_type == CHANGE_REMOVED:
            entity = entities.pop(item_id)
            await entity.async_remove()
            return

        # CHANGE_UPDATED
        await entities[item_id].async_update_config(config)  # type: ignore

    collection.async_add_listener(_collection_changed)


@callback
def attach_entity_registry_cleaner(
    hass: HomeAssistantType,
    domain: str,
    platform: str,
    collection: ObservableCollection,
) -> None:
    """Attach a listener to clean up entity registry on collection changes."""

    async def _collection_changed(change_type: str, item_id: str, config: Dict) -> None:
        """Handle a collection change: clean up entity registry on removals."""
        if change_type != CHANGE_REMOVED:
            return

        ent_reg = await entity_registry.async_get_registry(hass)
        ent_to_remove = ent_reg.async_get_entity_id(domain, platform, item_id)
        if ent_to_remove is not None:
            ent_reg.async_remove(ent_to_remove)

    collection.async_add_listener(_collection_changed)


class StorageCollectionWebsocket:
    """Class to expose storage collection management over websocket."""

    def __init__(
        self,
        storage_collection: StorageCollection,
        api_prefix: str,
        model_name: str,
        create_schema: dict,
        update_schema: dict,
    ):
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
