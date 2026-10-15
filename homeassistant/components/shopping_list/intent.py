"""Intents for the Shopping List integration."""

from typing import cast, override

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent

from .common import NoMatchingShoppingListItem, _get_shopping_data
from .const import DOMAIN

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

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        item_name = slots["item"]["value"].strip()
        shopping_data = _get_shopping_data(intent_obj.hass)
        completed_match = None
        normalized_name = item_name.casefold()
        for item in shopping_data.items:
            name = item["name"]
            if not isinstance(name, str) or name.casefold() != normalized_name:
                continue
            if not item["complete"]:
                return intent_obj.create_response()
            if completed_match is None:
                completed_match = item

        if completed_match is None:
            await shopping_data.async_add(item_name)
        else:
            await shopping_data.async_update(
                cast(str, completed_match["id"]),
                {"name": cast(str, completed_match["name"]), "complete": False},
            )

        return intent_obj.create_response()


class CompleteItemIntent(intent.IntentHandler):
    """Handle CompleteItem intents."""

    intent_type = INTENT_COMPLETE_ITEM
    description = "Marks an item as completed on the shopping list"
    slot_schema = {"item": cv.string}
    platforms = {DOMAIN}

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"].strip()

        try:
            complete_items = await _get_shopping_data(intent_obj.hass).async_complete(
                item
            )
        except NoMatchingShoppingListItem:
            complete_items = []

        response = intent_obj.create_response()
        response.async_set_speech_slots({"completed_items": complete_items})

        return response


class ListTopItemsIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_LAST_ITEMS
    description = "List the top five items on the shopping list"
    slot_schema = {"item": cv.string}
    platforms = {DOMAIN}

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        items = _get_shopping_data(intent_obj.hass).items[-5:]
        response: intent.IntentResponse = intent_obj.create_response()

        if not items:
            response.async_set_speech("There are no items on your shopping list")
        else:
            items_list = ", ".join(str(itm["name"]) for itm in reversed(items))
            response.async_set_speech(
                "These are the top"
                f" {min(len(items), 5)} items on your"
                f" shopping list: {items_list}"
            )
        return response
