"""Component to manage a scheduler."""
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

DOMAIN = 'scheduler'
DEPENDENCIES = ['http']
_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: {}}, extra=vol.ALLOW_EXTRA)
EVENT = 'scheduler_updated'
INTENT_ADD_ITEM = 'HassSchedulerAddItem'
INTENT_LAST_ITEMS = 'HassSchedulerLastItems'
ITEM_UPDATE_SCHEMA = vol.Schema({
    'complete': bool,
    'name': str,
})
PERSISTENCE = '.scheduler.json'


EVENT_SCHEMA = vol.Schema({
    vol.Required('title'): cv.string,
    vol.Required('start'): cv.string,
    vol.Optional('end'): cv.string,
    vol.Optional('url'): cv.string,
    vol.Optional('color'): cv.string,
    vol.Optional('all_day'): cv.boolean,
    vol.Optional('description'): cv.string,
})


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the scheduler."""
    data = hass.data[DOMAIN] = EventData(hass)
    yield from data.async_load()

    hass.http.register_view(SchedulerView)

    async def create_event(call):
        title = call.data.get("title")
        start = call.data.get("start")
        end = call.data.get("end")
        url = call.data.get("url")
        color = call.data.get("color")
        all_day = call.data.get("all_day", False)
        description = call.data.get("description")

        hass.data[DOMAIN].async_add(title, start, end, url, color, all_day, description)
        hass.bus.async_fire(EVENT)

    hass.services.async_register(DOMAIN, 'create_event', create_event, schema=EVENT_SCHEMA)

    async def delete_event(call):
        title = call.data.get("title")
        start = call.data.get("start")

        hass.data[DOMAIN].async_delete(title, start)
        hass.bus.async_fire(EVENT)

    hass.services.async_register(DOMAIN, 'delete_event', delete_event, schema=EVENT_SCHEMA)

    yield from hass.components.frontend.async_register_built_in_panel(
        'scheduler', 'Scheduler', 'mdi:calendar')

    return True


class EventData:
    """Class to hold scheduler data."""

    def __init__(self, hass):
        """Initialize the scheduler."""
        self.hass = hass
        self.items = []

    def _get_item(self, title, start):
        # Check if the object exists
        for item in self.items:
            if title == item['title'] and start == item['start']:
                # Item already created
                return item
        return None

    @callback
    def async_add(self, title, start, end=None, url=None, color=None, all_day=False, description=None):
        """Add a scheduler item."""
        # Check if the object exists
        if self._get_item(title, start) is not None:
            return
        # Create new item
        item = {
            'title': title,
            'start': start,
            'all_day': all_day,
            'id': uuid.uuid4().hex,
        }
        for key in ('end', 'url', 'color', 'description'):
            value = locals().get(key)
            if value is not None:
                item[key] = value
        self.items.append(item)
        self.hass.async_add_job(self.save)
        return item

    @callback
    def async_update(self, item_id, info):
        """Update a scheduler item."""
        # Check if the object exists
        item = next((itm for itm in self.items if itm['id'] == item_id), None)

        if item is None:
            raise KeyError

        info = ITEM_UPDATE_SCHEMA(info)
        item.update(info)
        self.hass.async_add_job(self.save)
        return item

    @callback
    def async_delete(self, title, date):
        """Clear completed items."""
        # TODO
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


# TODO Add Intent
class SchedulerView(http.HomeAssistantView):
    """View to retrieve scheduler content."""

    url = '/api/scheduler'
    name = "api:scheduler"

    @callback
    def get(self, request):
        """Retrieve scheduler items."""
        return self.json(request.app['hass'].data[DOMAIN].items)
