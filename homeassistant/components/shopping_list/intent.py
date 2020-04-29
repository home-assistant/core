"""Intents for the Shopping List integration."""
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv

from . import DOMAIN, EVENT

INTENT_ADD_ITEM = "HassShoppingListAddItem"
INTENT_LAST_ITEMS = "HassShoppingListLastItems"


async def async_setup_intents(hass):
    """Set up the Shopping List intents."""
    intent.async_register(hass, AddItemIntent())
    intent.async_register(hass, ListTopItemsIntent())


class AddItemIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_ADD_ITEM
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"]
        intent_obj.hass.data[DOMAIN].async_add(item)

        response = intent_obj.create_response()
        response.async_set_speech(f"Dodano {item} do twojej listy zakupów")
        intent_obj.hass.bus.async_fire(EVENT)
        return response


class ListTopItemsIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_LAST_ITEMS
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        items = intent_obj.hass.data[DOMAIN].items[-5:]
        response = intent_obj.create_response()

        if not items:
            response.async_set_speech("Nie ma elementów na liście zakupów.")
        else:
            if len(items) == 1:
                response.async_set_speech(
                    "Masz {} na liście zakupów.".format(
                        "".join(itm["name"] for itm in reversed(items))
                    )
                )
            else:
                response.async_set_speech(
                    "Oto najnowsze {} elementy na liście zakupów: {}".format(
                        min(len(items), 5),
                        ", ".join(itm["name"] for itm in reversed(items)),
                    )
                )
        return response
