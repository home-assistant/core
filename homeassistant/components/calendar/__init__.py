"""
Support for Google Calendar event device sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/calendar/
"""
import logging
from datetime import timedelta
import re

from aiohttp import web

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


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'calendar'

DEPENDENCIES = ['http']

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup(hass, config):
    """Track states and offer events for calendars."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, DOMAIN)

    hass.http.register_view(CalendarListView(component))
    hass.http.register_view(CalendarEventView(component))

    # Doesn't work in prod builds of the frontend: home-assistant-polymer#1289
    # await hass.components.frontend.async_register_built_in_panel(
    #     'calendar', 'calendar', 'hass:calendar')

    await component.async_setup(config)
    return True


DEFAULT_CONF_TRACK_NEW = True
DEFAULT_CONF_OFFSET = '!!'


def get_date(date):
    """Get the dateTime from date or dateTime as a local."""
    if 'date' in date:
        return dt.start_of_local_day(dt.dt.datetime.combine(
            dt.parse_date(date['date']), dt.dt.time.min))
    return dt.as_local(dt.parse_datetime(date['dateTime']))


class CalendarEventDevice(Entity):
    """A calendar event device."""

    # Classes overloading this must set data to an object
    # with an update() method
    data = None

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

        start = get_date(self.data.event['start'])
        end = get_date(self.data.event['end'])

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


class CalendarEventView(http.HomeAssistantView):
    """View to retrieve calendar content."""

    url = '/api/calendars/{entity_id}'
    name = 'api:calendars:calendar'

    def __init__(self, component):
        """Initialize calendar view."""
        self.component = component

    async def get(self, request, entity_id):
        """Return calendar events."""
        entity = self.component.get_entity(entity_id)
        start = request.query.get('start')
        end = request.query.get('end')
        if None in (start, end, entity):
            return web.Response(status=400)
        try:
            start_date = dt.parse_datetime(start)
            end_date = dt.parse_datetime(end)
        except (ValueError, AttributeError):
            return web.Response(status=400)
        event_list = await entity.async_get_events(
            request.app['hass'], start_date, end_date)
        return self.json(event_list)


class CalendarListView(http.HomeAssistantView):
    """View to retrieve calendar list."""

    url = '/api/calendars'
    name = "api:calendars"

    def __init__(self, component):
        """Initialize calendar view."""
        self.component = component

    async def get(self, request):
        """Retrieve calendar list."""
        get_state = request.app['hass'].states.get
        calendar_list = []

        for entity in self.component.entities:
            state = get_state(entity.entity_id)
            calendar_list.append({
                "name": state.name,
                "entity_id": entity.entity_id,
            })

        return self.json(sorted(calendar_list, key=lambda x: x['name']))
