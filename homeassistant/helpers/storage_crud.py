"""Helper to deal with YAML + storage."""
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional, cast

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components import websocket_api
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util.id import IDManager

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
        # New config (None if removed)
        Optional[dict],
    ],
    None,
]  # pylint: disable=invalid-name


class StorageCollection(ABC):
    """Offer a CRUD interface on top of JSON storage."""

    def __init__(self, store: Store, id_manager: Optional[IDManager] = None):
        """Initiate the storage collection."""
        self.store = store
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

    @callback
    def notify_change(
        self, change_type: str, item_id: str, item: Optional[dict]
    ) -> None:
        """Notify listeners of a change."""
        for listener in self.listeners:
            listener(change_type, item_id, item)

    async def async_initialize(self) -> None:
        """Initialize th Storage Manager."""
        raw_storage = cast(Optional[dict], await self.store.async_load())

        if raw_storage is None:
            raw_storage = {"items": []}

        for item in raw_storage["items"]:
            self.data[item[CONF_ID]] = item
            self.notify_change(CHANGE_ADDED, item[CONF_ID], item)

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
        self.notify_change(CHANGE_ADDED, item[CONF_ID], item)
        return item

    async def async_update_item(self, item_id: str, updates: dict) -> dict:
        """Update item."""
        current = self.data.get(item_id)

        if current is None:
            raise ValueError("Invalid item specified.")

        if CONF_ID in updates:
            if self.id_manager.has_id(updates[CONF_ID]):
                raise ValueError("ID already exists")

        updated = await self._update_data(current, updates)

        if CONF_ID in updates:
            self.data.pop(current[CONF_ID])

        self.data[item_id] = updated
        self._async_schedule_save()

        self.notify_change(CHANGE_UPDATED, item_id, updated)

        return self.data[item_id]

    async def async_delete_item(self, item_id: str) -> None:
        """Delete item."""
        if item_id not in self.data:
            raise ValueError("Invalid item specified.")

        self.data.pop(item_id)
        self._async_schedule_save()

        self.notify_change(CHANGE_REMOVED, item_id, None)

    @callback
    def _async_schedule_save(self) -> None:
        """Schedule saving the area registry."""
        self.store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict:
        """Return data of area registry to store in a file."""
        return {"items": list(self.data.values())}


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
    def async_initialize(self, hass: HomeAssistant) -> None:
        """Initialize the websocket commands."""
        websocket_api.async_register_command(
            hass,
            websocket_api.websocket_command(
                {vol.Required("type"): f"{self.api_prefix}/list"}
            )(self.ws_list_item),
        )

        websocket_api.async_register_command(
            hass,
            websocket_api.websocket_command(
                {
                    **self.create_schema,
                    vol.Required("type"): f"{self.api_prefix}/create",
                }
            )(self.ws_create_item),
        )

        websocket_api.async_register_command(
            hass,
            websocket_api.websocket_command(
                {
                    **self.update_schema,
                    vol.Required("type"): f"{self.api_prefix}/update",
                    vol.Required(self.item_id_key): str,
                }
            )(self.ws_update_item),
        )

        websocket_api.async_register_command(
            hass,
            websocket_api.websocket_command(
                {
                    vol.Required("type"): f"{self.api_prefix}/delete",
                    vol.Required(self.item_id_key): str,
                }
            )(self.ws_delete_item),
        )

    def ws_list_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """List items."""
        connection.send_result(msg["id"], self.storage_collection.async_items())

    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_create_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Create a item."""
        try:
            data = dict(msg)
            data.pop("id")
            data.pop("type")
            item = await self.storage_collection.async_create_item(**data,)
            connection.send_result(msg["id"], item)
        except vol.Invalid as err:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_INVALID_FORMAT,
                humanize_error(msg, err),
            )
        except ValueError as err:
            connection.send_error(
                msg["id"], websocket_api.const.ERR_INVALID_FORMAT, str(err)
            )

    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_update_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Update a item."""
        data = dict(msg)
        msg_id = data.pop("id")
        item_id = data.pop(self.item_id_key)
        data.pop("type")

        try:
            item = await self.storage_collection.async_update_item(item_id, **data)
            connection.send_result(msg_id, item)
        except ValueError as err:
            connection.send_error(
                msg_id, websocket_api.const.ERR_INVALID_FORMAT, str(err)
            )

    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_delete_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Delete a item."""
        await self.storage_collection.async_delete_item(msg[self.item_id_key])
        connection.send_result(msg["id"])
