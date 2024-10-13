"""Intents for the Shopping List integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv

from . import DOMAIN, EVENT_SHOPPING_LIST_UPDATED

INTENT_ADD_ITEM = "HassShoppingListAddItem"
INTENT_LAST_ITEMS = "HassShoppingListLastItems"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the Shopping List intents."""
    intent.async_register(hass, AddItemIntent())
    intent.async_register(hass, ListTopItemsIntent())


class AddItemIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_ADD_ITEM
    description = "Adds an item to the shopping list"
    slot_schema = {"item": cv.string}
    platforms = {DOMAIN}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"]
        await intent_obj.hass.data[DOMAIN].async_add(item)

        response = intent_obj.create_response()
        intent_obj.hass.bus.async_fire(EVENT_SHOPPING_LIST_UPDATED)
        return response


class ListTopItemsIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_LAST_ITEMS
    description = "List the top five items on the shopping list"
    slot_schema = {"item": cv.string}
    platforms = {DOMAIN}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        items = intent_obj.hass.data[DOMAIN].items[-5:]
        response = intent_obj.create_response()

        if not items:
            response.async_set_speech("There are no items on your shopping list")
        else:
            items_list = ", ".join(itm["name"] for itm in reversed(items))
            response.async_set_speech(
                f"These are the top {min(len(items), 5)} items on your shopping list: {items_list}"
            )
        return response
