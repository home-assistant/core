import asyncio
import logging

import voluptuous as vol

from homeassistant.components.intent import IntentHandler
import homeassistant.helpers.config_validation as cv


DOMAIN = 'shopping_list'
DEPENDENCIES = ['intent']
_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: {}}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the shopping list."""
    hass.data[DOMAIN] = []
    hass.intent.async_register(AddItemIntent())
    hass.intent.async_register(ListTopItemsIntent())
    return True


class AddItemIntent(IntentHandler):
    """Handle AddItem intents."""

    intent_type = 'ShoppingListAddItem'
    slot_schema = {
        'item': cv.string
    }

    @asyncio.coroutine
    def async_handle(self, intent):
        """Handle the intent."""
        print(intent.slots)
        slots = self.async_validate_slots(intent.slots)
        item = slots['item']['value']
        intent.hass.data[DOMAIN].append(item)

        response = intent.create_response()
        response.async_set_speech(
            "I've added {} to your shopping list".format(item))
        return response


class ListTopItemsIntent(IntentHandler):
    """Handle AddItem intents."""

    intent_type = 'ShoppingListLastItems'
    slot_schema = {
        'item': cv.string
    }

    @asyncio.coroutine
    def async_handle(self, intent):
        """Handle the intent."""
        response = intent.create_response()
        response.async_set_speech(
            "These are the top 5 items in your shopping list: {}".format(
                ', '.join(reversed(intent.hass.data[DOMAIN][-5:]))))
        return response
