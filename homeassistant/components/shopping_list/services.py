"""Support for shopping list services."""

from enum import StrEnum

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .common import NoMatchingShoppingListItem, _get_shopping_data
from .const import DEFAULT_REVERSE, DOMAIN


class ShoppingListService(StrEnum):
    """Store keys for shopping list services."""

    ADD_ITEM = "add_item"
    CLEAR_COMPLETED_ITEMS = "clear_completed_items"
    COMPLETE_ALL = "complete_all"
    COMPLETE_ITEM = "complete_item"
    INCOMPLETE_ALL = "incomplete_all"
    INCOMPLETE_ITEM = "incomplete_item"
    REMOVE_ITEM = "remove_item"
    SORT = "sort"


class ShoppingListServiceArgument(StrEnum):
    """Store keys for shopping list service arguments."""

    NAME = "name"
    REVERSE = "reverse"


SERVICE_ITEM_SCHEMA = probatio.Schema(
    {probatio.Required(ShoppingListServiceArgument.NAME): cv.string}
)
SERVICE_LIST_SCHEMA = probatio.Schema({})
SERVICE_SORT_SCHEMA = probatio.Schema(
    {
        probatio.Optional(
            ShoppingListServiceArgument.REVERSE, default=DEFAULT_REVERSE
        ): bool
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register shopping list services."""

    async def add_item_service(call: ServiceCall) -> None:
        """Add an item with `name`."""
        await _get_shopping_data(hass).async_add(
            call.data[ShoppingListServiceArgument.NAME]
        )

    async def remove_item_service(call: ServiceCall) -> None:
        """Remove the first item with matching `name`."""
        data = _get_shopping_data(hass)
        name = call.data[ShoppingListServiceArgument.NAME]

        try:
            item = [item for item in data.items if item["name"] == name][0]
        except IndexError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="item_not_found",
                translation_placeholders={"name": name},
            ) from err
        else:
            await data.async_remove(str(item["id"]))

    async def complete_item_service(call: ServiceCall) -> None:
        """Mark the first item with matching `name` as completed."""
        name = call.data[ShoppingListServiceArgument.NAME]
        try:
            await _get_shopping_data(hass).async_complete(name)
        except NoMatchingShoppingListItem as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="item_not_found",
                translation_placeholders={"name": name},
            ) from err

    async def incomplete_item_service(call: ServiceCall) -> None:
        """Mark the first item with matching `name` as incomplete."""
        data = _get_shopping_data(hass)
        name = call.data[ShoppingListServiceArgument.NAME]

        try:
            item = [item for item in data.items if item["name"] == name][0]
        except IndexError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="item_not_found",
                translation_placeholders={"name": name},
            ) from err
        else:
            await data.async_update(str(item["id"]), {"name": name, "complete": False})

    async def complete_all_service(call: ServiceCall) -> None:
        """Mark all items in the list as complete."""
        await _get_shopping_data(hass).async_update_list({"complete": True})

    async def incomplete_all_service(call: ServiceCall) -> None:
        """Mark all items in the list as incomplete."""
        await _get_shopping_data(hass).async_update_list({"complete": False})

    async def clear_completed_items_service(call: ServiceCall) -> None:
        """Clear all completed items from the list."""
        await _get_shopping_data(hass).async_clear_completed()

    async def sort_list_service(call: ServiceCall) -> None:
        """Sort all items by name."""
        await _get_shopping_data(hass).async_sort(
            call.data[ShoppingListServiceArgument.REVERSE]
        )

    hass.services.async_register(
        DOMAIN,
        ShoppingListService.ADD_ITEM,
        add_item_service,
        schema=SERVICE_ITEM_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        ShoppingListService.REMOVE_ITEM,
        remove_item_service,
        schema=SERVICE_ITEM_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        ShoppingListService.COMPLETE_ITEM,
        complete_item_service,
        schema=SERVICE_ITEM_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        ShoppingListService.INCOMPLETE_ITEM,
        incomplete_item_service,
        schema=SERVICE_ITEM_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        ShoppingListService.COMPLETE_ALL,
        complete_all_service,
        schema=SERVICE_LIST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        ShoppingListService.INCOMPLETE_ALL,
        incomplete_all_service,
        schema=SERVICE_LIST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        ShoppingListService.CLEAR_COMPLETED_ITEMS,
        clear_completed_items_service,
        schema=SERVICE_LIST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        ShoppingListService.SORT,
        sort_list_service,
        schema=SERVICE_SORT_SCHEMA,
    )
