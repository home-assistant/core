"""Support to manage a shopping list."""

from http import HTTPStatus
import logging
from typing import Any

from aiohttp import web
import probatio

from homeassistant.components import http, websocket_api
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .common import (
    NoMatchingShoppingListItem,
    ShoppingData,
    ShoppingListConfigEntry,
    _get_shopping_data,
)
from .const import DOMAIN
from .services import async_setup_services

PLATFORMS = [Platform.TODO]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

__all__ = [
    "DOMAIN",
    "ShoppingData",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the shopping list."""
    async_setup_services(hass)

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ShoppingListConfigEntry
) -> None:
    """Set up shopping list from config flow."""
    data = config_entry.runtime_data = ShoppingData(hass)
    await data.async_load()

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


class ShoppingListView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = "/api/shopping_list"
    name = "api:shopping_list"

    @callback
    def get(self, request: web.Request) -> web.Response:
        """Retrieve shopping list items."""
        return self.json(_get_shopping_data(request.app[http.KEY_HASS]).items)


class UpdateShoppingListItemView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = "/api/shopping_list/item/{item_id}"
    name = "api:shopping_list:item:id"

    async def post(self, request: web.Request, item_id: str) -> web.Response:
        """Update a shopping list item."""
        data = await request.json()
        shopping_data = _get_shopping_data(request.app[http.KEY_HASS])

        try:
            item = await shopping_data.async_update(item_id, data)
            return self.json(item)
        except NoMatchingShoppingListItem:
            return self.json_message("Item not found", HTTPStatus.NOT_FOUND)
        except probatio.Invalid:
            return self.json_message("Item not found", HTTPStatus.BAD_REQUEST)


class CreateShoppingListItemView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = "/api/shopping_list/item"
    name = "api:shopping_list:item"

    @RequestDataValidator(probatio.Schema({probatio.Required("name"): str}))
    async def post(self, request: web.Request, data: dict[str, str]) -> web.Response:
        """Create a new shopping list item."""
        shopping_data = _get_shopping_data(request.app[http.KEY_HASS])
        item = await shopping_data.async_add(data["name"])
        return self.json(item)


class ClearCompletedItemsView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = "/api/shopping_list/clear_completed"
    name = "api:shopping_list:clear_completed"

    async def post(self, request: web.Request) -> web.Response:
        """Retrieve if API is running."""
        shopping_data = _get_shopping_data(request.app[http.KEY_HASS])
        await shopping_data.async_clear_completed()
        return self.json_message("Cleared completed items.")


@callback
@websocket_api.websocket_command({probatio.Required("type"): "shopping_list/items"})
def websocket_handle_items(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle getting shopping_list items."""
    connection.send_message(
        websocket_api.result_message(msg["id"], _get_shopping_data(hass).items)
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "shopping_list/items/add",
        probatio.Required("name"): str,
    }
)
@websocket_api.async_response
async def websocket_handle_add(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle adding item to shopping_list."""
    item = await _get_shopping_data(hass).async_add(
        msg["name"], context=connection.context(msg)
    )
    connection.send_message(websocket_api.result_message(msg["id"], item))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "shopping_list/items/remove",
        probatio.Required("item_id"): str,
    }
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
        item = await _get_shopping_data(hass).async_remove(
            item_id, connection.context(msg)
        )
    except NoMatchingShoppingListItem:
        connection.send_message(
            websocket_api.error_message(msg_id, "item_not_found", "Item not found")
        )
        return

    connection.send_message(websocket_api.result_message(msg_id, item))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "shopping_list/items/update",
        probatio.Required("item_id"): str,
        probatio.Optional("name"): str,
        probatio.Optional("complete"): bool,
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
        item = await _get_shopping_data(hass).async_update(
            item_id, data, connection.context(msg)
        )
    except NoMatchingShoppingListItem:
        connection.send_message(
            websocket_api.error_message(msg_id, "item_not_found", "Item not found")
        )
        return

    connection.send_message(websocket_api.result_message(msg_id, item))


@websocket_api.websocket_command(
    {probatio.Required("type"): "shopping_list/items/clear"}
)
@websocket_api.async_response
async def websocket_handle_clear(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle clearing shopping_list items."""
    shopping_data = _get_shopping_data(hass)
    await shopping_data.async_clear_completed(connection.context(msg))
    connection.send_message(websocket_api.result_message(msg["id"]))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "shopping_list/items/reorder",
        probatio.Required("item_ids"): [str],
    }
)
@websocket_api.async_response
async def websocket_handle_reorder(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle reordering shopping_list items."""
    msg_id = msg.pop("id")
    try:
        shopping_data = _get_shopping_data(hass)
        await shopping_data.async_reorder(msg.pop("item_ids"), connection.context(msg))
    except NoMatchingShoppingListItem:
        connection.send_error(
            msg_id,
            websocket_api.ERR_NOT_FOUND,
            "One or more item id(s) not found.",
        )
        return
    except probatio.Invalid as err:
        connection.send_error(msg_id, websocket_api.ERR_INVALID_FORMAT, f"{err}")
        return

    connection.send_result(msg_id)
