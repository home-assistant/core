"""Component to manage a shoppling list."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components import http
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv


DOMAIN = 'shopping_list'
DEPENDENCIES = ['http']
_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: {}}, extra=vol.ALLOW_EXTRA)
EVENT = 'shopping_list_updated'
INTENT_ADD_ITEM = 'HassShoppingListAddItem'
INTENT_LAST_ITEMS = 'HassShoppingListLastItems'


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the shopping list."""
    hass.data[DOMAIN] = []
    intent.async_register(hass, AddItemIntent())
    intent.async_register(hass, ListTopItemsIntent())
    hass.http.register_view(ShoppingListView)
    hass.components.conversation.async_register(INTENT_ADD_ITEM, [
        'Add {item} to my shopping list',
    ])
    hass.components.conversation.async_register(INTENT_LAST_ITEMS, [
        'What is on my shopping list'
    ])
    hass.components.frontend.register_built_in_panel(
        'shopping-list', 'Shopping List', 'mdi:cart')
    return True


class AddItemIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_ADD_ITEM
    slot_schema = {
        'item': cv.string
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots['item']['value']
        intent_obj.hass.data[DOMAIN].append(item)

        response = intent_obj.create_response()
        response.async_set_speech(
            "I've added {} to your shopping list".format(item))
        intent_obj.hass.bus.async_fire(EVENT)
        return response


class ListTopItemsIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_LAST_ITEMS
    slot_schema = {
        'item': cv.string
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        response = intent_obj.create_response()
        response.async_set_speech(
            "These are the top 5 items in your shopping list: {}".format(
                ', '.join(reversed(intent_obj.hass.data[DOMAIN][-5:]))))
        intent_obj.hass.bus.async_fire(EVENT)
        return response


class ShoppingListView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = '/api/shopping_list'
    name = "api:shopping_list"

    @callback
    def get(self, request):
        """Retrieve if API is running."""
        return self.json(request.app['hass'].data[DOMAIN])
