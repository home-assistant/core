"""Intents for the Shopping List integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

INTENT_LAST_ITEMS = "HassShoppingListLastItems"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the Shopping List intents."""
    intent.async_register(hass, ListTopItemsIntent())


class ListTopItemsIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_LAST_ITEMS
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj: intent.Intent):
        """Handle the intent."""
        items = intent_obj.hass.data[DOMAIN].items[-5:]
        response = intent_obj.create_response()

        if not items:
            response.async_set_speech("There are no items on your shopping list")
        else:
            response.async_set_speech(
                "These are the top {} items on your shopping list: {}".format(
                    min(len(items), 5),
                    ", ".join(itm["name"] for itm in reversed(items)),
                )
            )
        return response
