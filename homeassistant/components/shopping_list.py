"""Component to manage a shopping list."""
import asyncio
import logging
import uuid

import voluptuous as vol

from homeassistant.const import HTTP_NOT_FOUND, HTTP_BAD_REQUEST
from homeassistant.core import callback
from homeassistant.components import http
from homeassistant.components.http.data_validator import (
    RequestDataValidator)
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json

ATTR_NAME = 'name'

DOMAIN = 'shopping_list'
DEPENDENCIES = ['http']
_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: {}}, extra=vol.ALLOW_EXTRA)
EVENT = 'shopping_list_updated'
INTENT_ADD_ITEM = 'HassShoppingListAddItem'
INTENT_LAST_ITEMS = 'HassShoppingListLastItems'
ITEM_UPDATE_SCHEMA = vol.Schema({
    'complete': bool,
    ATTR_NAME: str,
})
PERSISTENCE = '.shopping_list.json'

SERVICE_ADD_ITEM = 'add_item'
SERVICE_COMPLETE_ITEM = 'complete_item'

SERVICE_ITEM_SCHEMA = vol.Schema({
    vol.Required(ATTR_NAME): vol.Any(None, cv.string)
})


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the shopping list."""
    @asyncio.coroutine
    def add_item_service(call):
        """Add an item with `name`."""
        data = hass.data[DOMAIN]
        name = call.data.get(ATTR_NAME)
        if name is not None:
            data.async_add(name)

    @asyncio.coroutine
    def complete_item_service(call):
        """Mark the item provided via `name` as completed."""
        data = hass.data[DOMAIN]
        name = call.data.get(ATTR_NAME)
        if name is None:
            return
        try:
            item = [item for item in data.items if item['name'] == name][0]
        except IndexError:
            _LOGGER.error("Removing of item failed: %s cannot be found", name)
        else:
            data.async_update(item['id'], {'name': name, 'complete': True})

    data = hass.data[DOMAIN] = ShoppingData(hass)
    yield from data.async_load()

    intent.async_register(hass, AddItemIntent())
    intent.async_register(hass, ListTopItemsIntent())

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_ITEM, add_item_service, schema=SERVICE_ITEM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_COMPLETE_ITEM, complete_item_service,
        schema=SERVICE_ITEM_SCHEMA
    )

    hass.http.register_view(ShoppingListView)
    hass.http.register_view(CreateShoppingListItemView)
    hass.http.register_view(UpdateShoppingListItemView)
    hass.http.register_view(ClearCompletedItemsView)

    hass.components.conversation.async_register(INTENT_ADD_ITEM, [
        'Add [the] [a] [an] {item} to my shopping list',
    ])
    hass.components.conversation.async_register(INTENT_LAST_ITEMS, [
        'What is on my shopping list'
    ])

    yield from hass.components.frontend.async_register_built_in_panel(
        'shopping-list', 'shopping_list', 'mdi:cart')

    return True


class ShoppingData:
    """Class to hold shopping list data."""

    def __init__(self, hass):
        """Initialize the shopping list."""
        self.hass = hass
        self.items = []

    @callback
    def async_add(self, name):
        """Add a shopping list item."""
        item = {
            'name': name,
            'id': uuid.uuid4().hex,
            'complete': False
        }
        self.items.append(item)
        self.hass.async_add_job(self.save)
        return item

    @callback
    def async_update(self, item_id, info):
        """Update a shopping list item."""
        item = next((itm for itm in self.items if itm['id'] == item_id), None)

        if item is None:
            raise KeyError

        info = ITEM_UPDATE_SCHEMA(info)
        item.update(info)
        self.hass.async_add_job(self.save)
        return item

    @callback
    def async_clear_completed(self):
        """Clear completed items."""
        self.items = [itm for itm in self.items if not itm['complete']]
        self.hass.async_add_job(self.save)

    @asyncio.coroutine
    def async_load(self):
        """Load items."""
        def load():
            """Load the items synchronously."""
            return load_json(self.hass.config.path(PERSISTENCE), default=[])

        self.items = yield from self.hass.async_add_job(load)

    def save(self):
        """Save the items."""
        save_json(self.hass.config.path(PERSISTENCE), self.items)


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
        intent_obj.hass.data[DOMAIN].async_add(item)

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
        items = intent_obj.hass.data[DOMAIN].items[-5:]
        response = intent_obj.create_response()

        if not items:
            response.async_set_speech(
                "There are no items on your shopping list")
        else:
            response.async_set_speech(
                "These are the top {} items on your shopping list: {}".format(
                    min(len(items), 5),
                    ', '.join(itm['name'] for itm in reversed(items))))
        return response


class ShoppingListView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = '/api/shopping_list'
    name = "api:shopping_list"

    @callback
    def get(self, request):
        """Retrieve shopping list items."""
        return self.json(request.app['hass'].data[DOMAIN].items)


class UpdateShoppingListItemView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = '/api/shopping_list/item/{item_id}'
    name = "api:shopping_list:item:id"

    async def post(self, request, item_id):
        """Update a shopping list item."""
        data = await request.json()

        try:
            item = request.app['hass'].data[DOMAIN].async_update(item_id, data)
            request.app['hass'].bus.async_fire(EVENT)
            return self.json(item)
        except KeyError:
            return self.json_message('Item not found', HTTP_NOT_FOUND)
        except vol.Invalid:
            return self.json_message('Item not found', HTTP_BAD_REQUEST)


class CreateShoppingListItemView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = '/api/shopping_list/item'
    name = "api:shopping_list:item"

    @RequestDataValidator(vol.Schema({
        vol.Required('name'): str,
    }))
    @asyncio.coroutine
    def post(self, request, data):
        """Create a new shopping list item."""
        item = request.app['hass'].data[DOMAIN].async_add(data['name'])
        request.app['hass'].bus.async_fire(EVENT)
        return self.json(item)


class ClearCompletedItemsView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = '/api/shopping_list/clear_completed'
    name = "api:shopping_list:clear_completed"

    @callback
    def post(self, request):
        """Retrieve if API is running."""
        hass = request.app['hass']
        hass.data[DOMAIN].async_clear_completed()
        hass.bus.async_fire(EVENT)
        return self.json_message('Cleared completed items.')
