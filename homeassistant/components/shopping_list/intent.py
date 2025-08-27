"""Intents for the Shopping List integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent

from . import DOMAIN, EVENT_SHOPPING_LIST_UPDATED, NoMatchingShoppingListItem

INTENT_ADD_ITEM = "HassShoppingListAddItem"
INTENT_COMPLETE_ITEM = "HassShoppingListCompleteItem"
INTENT_LAST_ITEMS = "HassShoppingListLastItems"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the Shopping List intents."""
    intent.async_register(hass, AddItemIntent())
    intent.async_register(hass, CompleteItemIntent())
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
        item = slots["item"]["value"].strip()
        await intent_obj.hass.data[DOMAIN].async_add(item)

        response = intent_obj.create_response()
        intent_obj.hass.bus.async_fire(EVENT_SHOPPING_LIST_UPDATED)
        return response


class CompleteItemIntent(intent.IntentHandler):
    """Handle CompleteItem intents."""

    intent_type = INTENT_COMPLETE_ITEM
    description = "Marks an item as completed on the shopping list"
    slot_schema = {"item": cv.string}
    platforms = {DOMAIN}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"].strip()

        try:
            complete_items = await intent_obj.hass.data[DOMAIN].async_complete(item)
        except NoMatchingShoppingListItem:
            complete_items = []

        intent_obj.hass.bus.async_fire(EVENT_SHOPPING_LIST_UPDATED)

        response = intent_obj.create_response()
        response.async_set_speech_slots({"completed_items": complete_items})
        response.response_type = intent.IntentResponseType.ACTION_DONE

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
        response: intent.IntentResponse = intent_obj.create_response()

        if not items:
            response.async_set_speech("There are no items on your shopping list")
        else:
            items_list = ", ".join(itm["name"] for itm in reversed(items))
            response.async_set_speech(
                f"These are the top {min(len(items), 5)} items on your shopping list: {items_list}"
            )
        return response
