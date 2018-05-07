"""
Support for Google Calendar event device sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/calendar/
"""
import asyncio
import logging
from datetime import timedelta
import re

import voluptuous as vol

from homeassistant.components.google import (
    CONF_OFFSET, CONF_DEVICE_ID, CONF_NAME)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.helpers.config_validation import time_period_str
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.util import dt
from homeassistant.components import http
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json



_LOGGER = logging.getLogger(__name__)

DOMAIN = 'calendar'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SCAN_INTERVAL = timedelta(seconds=60)

EVENT_SCHEMA = vol.Schema({
    vol.Required('title'): cv.string,
    vol.Required('start'): cv.string,
    vol.Optional('end'): cv.string,
    vol.Optional('url'): cv.string,
    vol.Optional('color'): cv.string,
    vol.Optional('all_day'): cv.boolean,
    vol.Optional('description'): cv.string,
})

PERSISTENCE = '.calendar.json'


@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for calendars."""
    data = hass.data[DOMAIN] = CalendarData(hass)
    yield from data.async_load()

    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, DOMAIN)

    hass.http.register_view(CalendarView)

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
        'calendar', 'Calendar', 'mdi:calendar')


    yield from component.async_setup(config)
    return True


DEFAULT_CONF_TRACK_NEW = True
DEFAULT_CONF_OFFSET = '!!'


# pylint: disable=too-many-instance-attributes
class CalendarEventDevice(Entity):
    """A calendar event device."""

    # Classes overloading this must set data to an object
    # with an update() method
    data = None

    # pylint: disable=too-many-arguments
    def __init__(self, hass, data):
        """Create the Calendar Event Device."""
        self._name = data.get(CONF_NAME)
        self.dev_id = data.get(CONF_DEVICE_ID)
        self._offset = data.get(CONF_OFFSET, DEFAULT_CONF_OFFSET)
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, self.dev_id, hass=hass)

        self._cal_data = {
            'all_day': False,
            'offset_time': dt.dt.timedelta(),
            'message': '',
            'start': None,
            'end': None,
            'location': '',
            'description': '',
        }

        self.update()

    def offset_reached(self):
        """Have we reached the offset time specified in the event title."""
        if self._cal_data['start'] is None or \
           self._cal_data['offset_time'] == dt.dt.timedelta():
            return False

        return self._cal_data['start'] + self._cal_data['offset_time'] <= \
            dt.now(self._cal_data['start'].tzinfo)

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        start = self._cal_data.get('start', None)
        end = self._cal_data.get('end', None)
        start = start.strftime(DATE_STR_FORMAT) if start is not None else None
        end = end.strftime(DATE_STR_FORMAT) if end is not None else None

        return {
            'message': self._cal_data.get('message', ''),
            'all_day': self._cal_data.get('all_day', False),
            'offset_reached': self.offset_reached(),
            'start_time': start,
            'end_time': end,
            'location': self._cal_data.get('location', None),
            'description': self._cal_data.get('description', None),
        }

    @property
    def state(self):
        """Return the state of the calendar event."""
        start = self._cal_data.get('start', None)
        end = self._cal_data.get('end', None)
        if start is None or end is None:
            return STATE_OFF

        now = dt.now()

        if start <= now and end > now:
            return STATE_ON

        if now >= end:
            self.cleanup()

        return STATE_OFF

    def cleanup(self):
        """Cleanup any start/end listeners that were setup."""
        self._cal_data = {
            'all_day': False,
            'offset_time': 0,
            'message': '',
            'start': None,
            'end': None,
            'location': None,
            'description': None
        }

    def update(self):
        """Search for the next event."""
        if not self.data or not self.data.update():
            # update cached, don't do anything
            return

        if not self.data.event:
            # we have no event to work on, make sure we're clean
            self.cleanup()
            return

        def _get_date(date):
            """Get the dateTime from date or dateTime as a local."""
            if 'date' in date:
                return dt.start_of_local_day(dt.dt.datetime.combine(
                    dt.parse_date(date['date']), dt.dt.time.min))
            return dt.as_local(dt.parse_datetime(date['dateTime']))

        start = _get_date(self.data.event['start'])
        end = _get_date(self.data.event['end'])

        summary = self.data.event.get('summary', '')

        # check if we have an offset tag in the message
        # time is HH:MM or MM
        reg = '{}([+-]?[0-9]{{0,2}}(:[0-9]{{0,2}})?)'.format(self._offset)
        search = re.search(reg, summary)
        if search and search.group(1):
            time = search.group(1)
            if ':' not in time:
                if time[0] == '+' or time[0] == '-':
                    time = '{}0:{}'.format(time[0], time[1:])
                else:
                    time = '0:{}'.format(time)

            offset_time = time_period_str(time)
            summary = (summary[:search.start()] + summary[search.end():]) \
                .strip()
        else:
            offset_time = dt.dt.timedelta()  # default it

        # cleanup the string so we don't have a bunch of double+ spaces
        self._cal_data['message'] = re.sub('  +', '', summary).strip()

        self._cal_data['offset_time'] = offset_time
        self._cal_data['location'] = self.data.event.get('location', '')
        self._cal_data['description'] = self.data.event.get('description', '')
        self._cal_data['start'] = start
        self._cal_data['end'] = end
        self._cal_data['all_day'] = 'date' in self.data.event['start']


class CalendarData:
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


class CalendarView(http.HomeAssistantView):
    """View to retrieve calendar content."""

    url = '/api/calendar'
    name = "api:calendar"

    @callback
    def get(self, request):
        """Retrieve calendar items."""
        return self.json(request.app['hass'].data[DOMAIN].items)
