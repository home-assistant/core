"""Support to manage a shopping list."""

from __future__ import annotations

from collections.abc import Callable
from http import HTTPStatus
import logging
from typing import Any, cast
import uuid

from aiohttp import web
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import http, websocket_api
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, Platform
from homeassistant.core import Context, HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.json import save_json
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.json import JsonValueType, load_json_array

from .const import (
    ATTR_REVERSE,
    DEFAULT_REVERSE,
    DOMAIN,
    EVENT_SHOPPING_LIST_UPDATED,
    SERVICE_ADD_ITEM,
    SERVICE_CLEAR_COMPLETED_ITEMS,
    SERVICE_COMPLETE_ALL,
    SERVICE_COMPLETE_ITEM,
    SERVICE_INCOMPLETE_ALL,
    SERVICE_INCOMPLETE_ITEM,
    SERVICE_REMOVE_ITEM,
    SERVICE_SORT,
)

PLATFORMS = [Platform.TODO]

ATTR_COMPLETE = "complete"

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: {}}, extra=vol.ALLOW_EXTRA)
ITEM_UPDATE_SCHEMA = vol.Schema({ATTR_COMPLETE: bool, ATTR_NAME: str})
PERSISTENCE = ".shopping_list.json"

SERVICE_ITEM_SCHEMA = vol.Schema({vol.Required(ATTR_NAME): cv.string})
SERVICE_LIST_SCHEMA = vol.Schema({})
SERVICE_SORT_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_REVERSE, default=DEFAULT_REVERSE): bool}
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the shopping list."""

    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up shopping list from config flow."""

    async def add_item_service(call: ServiceCall) -> None:
        """Add an item with `name`."""
        data = hass.data[DOMAIN]
        await data.async_add(call.data[ATTR_NAME])

    async def remove_item_service(call: ServiceCall) -> None:
        """Remove the first item with matching `name`."""
        data = hass.data[DOMAIN]
        name = call.data[ATTR_NAME]

        try:
            item = [item for item in data.items if item["name"] == name][0]
        except IndexError:
            _LOGGER.error("Removing of item failed: %s cannot be found", name)
        else:
            await data.async_remove(item["id"])

    async def complete_item_service(call: ServiceCall) -> None:
        """Mark the first item with matching `name` as completed."""
        data = hass.data[DOMAIN]
        name = call.data[ATTR_NAME]

        try:
            item = [item for item in data.items if item["name"] == name][0]
        except IndexError:
            _LOGGER.error("Updating of item failed: %s cannot be found", name)
        else:
            await data.async_update(item["id"], {"name": name, "complete": True})

    async def incomplete_item_service(call: ServiceCall) -> None:
        """Mark the first item with matching `name` as incomplete."""
        data = hass.data[DOMAIN]
        name = call.data[ATTR_NAME]

        try:
            item = [item for item in data.items if item["name"] == name][0]
        except IndexError:
            _LOGGER.error("Restoring of item failed: %s cannot be found", name)
        else:
            await data.async_update(item["id"], {"name": name, "complete": False})

    async def complete_all_service(call: ServiceCall) -> None:
        """Mark all items in the list as complete."""
        await data.async_update_list({"complete": True})

    async def incomplete_all_service(call: ServiceCall) -> None:
        """Mark all items in the list as incomplete."""
        await data.async_update_list({"complete": False})

    async def clear_completed_items_service(call: ServiceCall) -> None:
        """Clear all completed items from the list."""
        await data.async_clear_completed()

    async def sort_list_service(call: ServiceCall) -> None:
        """Sort all items by name."""
        await data.async_sort(call.data[ATTR_REVERSE])

    data = hass.data[DOMAIN] = ShoppingData(hass)
    await data.async_load()

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_ITEM, add_item_service, schema=SERVICE_ITEM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_ITEM, remove_item_service, schema=SERVICE_ITEM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_COMPLETE_ITEM, complete_item_service, schema=SERVICE_ITEM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_INCOMPLETE_ITEM,
        incomplete_item_service,
        schema=SERVICE_ITEM_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPLETE_ALL,
        complete_all_service,
        schema=SERVICE_LIST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_INCOMPLETE_ALL,
        incomplete_all_service,
        schema=SERVICE_LIST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_COMPLETED_ITEMS,
        clear_completed_items_service,
        schema=SERVICE_LIST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SORT,
        sort_list_service,
        schema=SERVICE_SORT_SCHEMA,
    )

    hass.http.register_view(ShoppingListView)
    hass.http.register_view(CreateShoppingListItemView)
    hass.http.register_view(UpdateShoppingListItemView)
    hass.http.register_view(ClearCompletedItemsView)

    websocket_api.async_register_command(hass, websocket_handle_items)
    websocket_api.async_register_command(hass, websocket_handle_add)
    websocket_api.async_register_command(hass, websocket_handle_remove)
    websocket_api.async_register_command(hass, websocket_handle_update)
    websocket_api.async_register_command(hass, websocket_handle_clear)
    websocket_api.async_register_command(hass, websocket_handle_reorder)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


class NoMatchingShoppingListItem(Exception):
    """No matching item could be found in the shopping list."""


class ShoppingData:
    """Class to hold shopping list data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the shopping list."""
        self.hass = hass
        self.items: list[dict[str, JsonValueType]] = []
        self._listeners: list[Callable[[], None]] = []

    async def async_add(
        self, name: str | None, complete: bool = False, context: Context | None = None
    ) -> dict[str, JsonValueType]:
        """Add a shopping list item."""
        item: dict[str, JsonValueType] = {
            "name": name,
            "id": uuid.uuid4().hex,
            "complete": complete,
        }
        self.items.append(item)
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "add", "item": item},
            context=context,
        )
        return item

    async def async_remove(
        self, item_id: str, context: Context | None = None
    ) -> dict[str, JsonValueType] | None:
        """Remove a shopping list item."""
        removed = await self.async_remove_items(
            item_ids=set({item_id}), context=context
        )
        return next(iter(removed), None)

    async def async_remove_items(
        self, item_ids: set[str], context: Context | None = None
    ) -> list[dict[str, JsonValueType]]:
        """Remove a shopping list item."""
        items_dict: dict[str, dict[str, JsonValueType]] = {}
        for itm in self.items:
            item_id = cast(str, itm["id"])
            items_dict[item_id] = itm
        removed = []
        for item_id in item_ids:
            _LOGGER.debug(
                "Removing %s",
            )
            if not (item := items_dict.pop(item_id, None)):
                raise NoMatchingShoppingListItem(
                    "Item '{item_id}' not found in shopping list"
                )
            removed.append(item)
        self.items = list(items_dict.values())
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        for item in removed:
            self.hass.bus.async_fire(
                EVENT_SHOPPING_LIST_UPDATED,
                {"action": "remove", "item": item},
                context=context,
            )
        return removed

    async def async_update(
        self, item_id: str | None, info: dict[str, Any], context: Context | None = None
    ) -> dict[str, JsonValueType]:
        """Update a shopping list item."""
        item = next((itm for itm in self.items if itm["id"] == item_id), None)

        if item is None:
            raise NoMatchingShoppingListItem

        info = ITEM_UPDATE_SCHEMA(info)
        item.update(info)
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "update", "item": item},
            context=context,
        )
        return item

    async def async_clear_completed(self, context: Context | None = None) -> None:
        """Clear completed items."""
        self.items = [itm for itm in self.items if not itm["complete"]]
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "clear"},
            context=context,
        )

    async def async_update_list(
        self, info: dict[str, JsonValueType], context: Context | None = None
    ) -> list[dict[str, JsonValueType]]:
        """Update all items in the list."""
        for item in self.items:
            item.update(info)
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "update_list"},
            context=context,
        )
        return self.items

    @callback
    def async_reorder(
        self, item_ids: list[str], context: Context | None = None
    ) -> None:
        """Reorder items."""
        # The array for sorted items.
        new_items = []
        all_items_mapping = {item["id"]: item for item in self.items}
        # Append items by the order of passed in array.
        for item_id in item_ids:
            if item_id not in all_items_mapping:
                raise NoMatchingShoppingListItem
            new_items.append(all_items_mapping[item_id])
            # Remove the item from mapping after it's appended in the result array.
            del all_items_mapping[item_id]
        # Append the rest of the items
        for key in all_items_mapping:
            # All the unchecked items must be passed in the item_ids array,
            # so all items left in the mapping should be checked items.
            if all_items_mapping[key]["complete"] is False:
                raise vol.Invalid(
                    "The item ids array doesn't contain all the unchecked shopping list"
                    " items."
                )
            new_items.append(all_items_mapping[key])
        self.items = new_items
        self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "reorder"},
            context=context,
        )

    async def async_move_item(self, uid: str, previous: str | None = None) -> None:
        """Re-order a shopping list item."""
        if uid == previous:
            return
        item_idx = {cast(str, itm["id"]): idx for idx, itm in enumerate(self.items)}
        if uid not in item_idx:
            raise NoMatchingShoppingListItem(f"Item '{uid}' not found in shopping list")
        if previous and previous not in item_idx:
            raise NoMatchingShoppingListItem(
                f"Item '{previous}' not found in shopping list"
            )
        dst_idx = item_idx[previous] + 1 if previous else 0
        src_idx = item_idx[uid]
        src_item = self.items.pop(src_idx)
        if dst_idx > src_idx:
            dst_idx -= 1
        self.items.insert(dst_idx, src_item)
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "reorder"},
        )

    async def async_sort(
        self, reverse: bool = False, context: Context | None = None
    ) -> None:
        """Sort items by name."""
        self.items = sorted(self.items, key=lambda item: item["name"], reverse=reverse)  # type: ignore[arg-type,return-value]
        self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "sorted"},
            context=context,
        )

    async def async_load(self) -> None:
        """Load items."""

        def load() -> list[dict[str, JsonValueType]]:
            """Load the items synchronously."""
            return cast(
                list[dict[str, JsonValueType]],
                load_json_array(self.hass.config.path(PERSISTENCE)),
            )

        self.items = await self.hass.async_add_executor_job(load)

    def save(self) -> None:
        """Save the items."""
        save_json(self.hass.config.path(PERSISTENCE), self.items)

    def async_add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        """Add a listener to notify when data is updated."""

        def unsub() -> None:
            self._listeners.remove(cb)

        self._listeners.append(cb)
        return unsub

    def _async_notify(self) -> None:
        """Notify all listeners that data has been updated."""
        for listener in self._listeners:
            listener()


class ShoppingListView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = "/api/shopping_list"
    name = "api:shopping_list"

    @callback
    def get(self, request: web.Request) -> web.Response:
        """Retrieve shopping list items."""
        return self.json(request.app[http.KEY_HASS].data[DOMAIN].items)


class UpdateShoppingListItemView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = "/api/shopping_list/item/{item_id}"
    name = "api:shopping_list:item:id"

    async def post(self, request: web.Request, item_id: str) -> web.Response:
        """Update a shopping list item."""
        data = await request.json()
        hass = request.app[http.KEY_HASS]

        try:
            item = await hass.data[DOMAIN].async_update(item_id, data)
            return self.json(item)
        except NoMatchingShoppingListItem:
            return self.json_message("Item not found", HTTPStatus.NOT_FOUND)
        except vol.Invalid:
            return self.json_message("Item not found", HTTPStatus.BAD_REQUEST)


class CreateShoppingListItemView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = "/api/shopping_list/item"
    name = "api:shopping_list:item"

    @RequestDataValidator(vol.Schema({vol.Required("name"): str}))
    async def post(self, request: web.Request, data: dict[str, str]) -> web.Response:
        """Create a new shopping list item."""
        hass = request.app[http.KEY_HASS]
        item = await hass.data[DOMAIN].async_add(data["name"])
        return self.json(item)


class ClearCompletedItemsView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = "/api/shopping_list/clear_completed"
    name = "api:shopping_list:clear_completed"

    async def post(self, request: web.Request) -> web.Response:
        """Retrieve if API is running."""
        hass = request.app[http.KEY_HASS]
        await hass.data[DOMAIN].async_clear_completed()
        return self.json_message("Cleared completed items.")


@callback
@websocket_api.websocket_command({vol.Required("type"): "shopping_list/items"})
def websocket_handle_items(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle getting shopping_list items."""
    connection.send_message(
        websocket_api.result_message(msg["id"], hass.data[DOMAIN].items)
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "shopping_list/items/add", vol.Required("name"): str}
)
@websocket_api.async_response
async def websocket_handle_add(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle adding item to shopping_list."""
    item = await hass.data[DOMAIN].async_add(
        msg["name"], context=connection.context(msg)
    )
    connection.send_message(websocket_api.result_message(msg["id"], item))


@websocket_api.websocket_command(
    {vol.Required("type"): "shopping_list/items/remove", vol.Required("item_id"): str}
)
@websocket_api.async_response
async def websocket_handle_remove(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle removing shopping_list item."""
    msg_id = msg.pop("id")
    item_id = msg.pop("item_id")
    msg.pop("type")

    try:
        item = await hass.data[DOMAIN].async_remove(item_id, connection.context(msg))
    except NoMatchingShoppingListItem:
        connection.send_message(
            websocket_api.error_message(msg_id, "item_not_found", "Item not found")
        )
        return

    connection.send_message(websocket_api.result_message(msg_id, item))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "shopping_list/items/update",
        vol.Required("item_id"): str,
        vol.Optional("name"): str,
        vol.Optional("complete"): bool,
    }
)
@websocket_api.async_response
async def websocket_handle_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle updating shopping_list item."""
    msg_id = msg.pop("id")
    item_id = msg.pop("item_id")
    msg.pop("type")
    data = msg

    try:
        item = await hass.data[DOMAIN].async_update(
            item_id, data, connection.context(msg)
        )
    except NoMatchingShoppingListItem:
        connection.send_message(
            websocket_api.error_message(msg_id, "item_not_found", "Item not found")
        )
        return

    connection.send_message(websocket_api.result_message(msg_id, item))


@websocket_api.websocket_command({vol.Required("type"): "shopping_list/items/clear"})
@websocket_api.async_response
async def websocket_handle_clear(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle clearing shopping_list items."""
    await hass.data[DOMAIN].async_clear_completed(connection.context(msg))
    connection.send_message(websocket_api.result_message(msg["id"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "shopping_list/items/reorder",
        vol.Required("item_ids"): [str],
    }
)
def websocket_handle_reorder(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle reordering shopping_list items."""
    msg_id = msg.pop("id")
    try:
        hass.data[DOMAIN].async_reorder(msg.pop("item_ids"), connection.context(msg))
    except NoMatchingShoppingListItem:
        connection.send_error(
            msg_id,
            websocket_api.ERR_NOT_FOUND,
            "One or more item id(s) not found.",
        )
        return
    except vol.Invalid as err:
        connection.send_error(msg_id, websocket_api.ERR_INVALID_FORMAT, f"{err}")
        return

    connection.send_result(msg_id)
