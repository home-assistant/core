"""Support for shopping list services."""

import logging

import voluptuous as vol

from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .common import NoMatchingShoppingListItem, _get_shopping_data
from .const import (
    ATTR_REVERSE,
    DEFAULT_REVERSE,
    DOMAIN,
    SERVICE_ADD_ITEM,
    SERVICE_CLEAR_COMPLETED_ITEMS,
    SERVICE_COMPLETE_ALL,
    SERVICE_COMPLETE_ITEM,
    SERVICE_INCOMPLETE_ALL,
    SERVICE_INCOMPLETE_ITEM,
    SERVICE_REMOVE_ITEM,
    SERVICE_SORT,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_ITEM_SCHEMA = vol.Schema({vol.Required(ATTR_NAME): cv.string})
SERVICE_LIST_SCHEMA = vol.Schema({})
SERVICE_SORT_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_REVERSE, default=DEFAULT_REVERSE): bool}
)


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register shopping list services."""

    async def add_item_service(call: ServiceCall) -> None:
        """Add an item with `name`."""
        await _get_shopping_data(hass).async_add(call.data[ATTR_NAME])

    async def remove_item_service(call: ServiceCall) -> None:
        """Remove the first item with matching `name`."""
        data = _get_shopping_data(hass)
        name = call.data[ATTR_NAME]

        try:
            item = [item for item in data.items if item["name"] == name][0]
        # pylint: disable-next=home-assistant-action-swallowed-exception
        except IndexError:
            _LOGGER.error("Removing of item failed: %s cannot be found", name)
        else:
            await data.async_remove(str(item["id"]))

    async def complete_item_service(call: ServiceCall) -> None:
        """Mark the first item with matching `name` as completed."""
        name = call.data[ATTR_NAME]
        try:
            await _get_shopping_data(hass).async_complete(name)
        # pylint: disable-next=home-assistant-action-swallowed-exception
        except NoMatchingShoppingListItem:
            _LOGGER.error("Completing of item failed: %s cannot be found", name)

    async def incomplete_item_service(call: ServiceCall) -> None:
        """Mark the first item with matching `name` as incomplete."""
        data = _get_shopping_data(hass)
        name = call.data[ATTR_NAME]

        try:
            item = [item for item in data.items if item["name"] == name][0]
        # pylint: disable-next=home-assistant-action-swallowed-exception
        except IndexError:
            _LOGGER.error("Restoring of item failed: %s cannot be found", name)
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
        await _get_shopping_data(hass).async_sort(call.data[ATTR_REVERSE])

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
