"""Support for Google Calendar event device sensors."""
import logging
from datetime import timedelta, datetime
import re
from typing import Dict

from aiohttp import web
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.google import (
    CONF_DEVICE_ID, CONF_NAME)
from homeassistant.const import (
    STATE_OFF, STATE_ON, CONF_MAXIMUM, CONF_ENTITY_ID, CONF_TYPE)
from homeassistant.helpers.config_validation import (  # noqa
    PLATFORM_SCHEMA, PLATFORM_SCHEMA_BASE)
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt
from homeassistant.components import http


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'calendar'

DEPENDENCIES = ['http']

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup(hass, config):
    """Track states and offer events for calendars."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, DOMAIN)

    hass.http.register_view(CalendarListView(component))
    hass.http.register_view(CalendarEventView(component))

    # Doesn't work in prod builds of the frontend: home-assistant-polymer#1289
    # await hass.components.frontend.async_register_built_in_panel(
    #     'calendar', 'calendar', 'hass:calendar')

    hass.components.websocket_api.async_register_command(get_calendar_info)

    await component.async_setup(config)
    return True


def get_date(date):
    """Get the dateTime from date or dateTime as a local."""
    if 'date' in date:
        return dt.start_of_local_day(dt.dt.datetime.combine(
            dt.parse_date(date['date']), dt.dt.time.min))
    return dt.as_local(dt.parse_datetime(date['dateTime']))


def normalize_event(event):
    """Normalize a calendar event."""
    normalized_event = {}

    start = get_date(event['start'])
    end = get_date(event['end'])
    normalized_event['dt_start'] = start
    normalized_event['dt_end'] = end

    # save io foramtted date string
    start_formatted = start.isoformat() if start is not None else None
    end_formatted = end.isoformat() if end is not None else None
    normalized_event['start'] = start_formatted
    normalized_event['end'] = end_formatted

    # cleanup the string so we don't have a bunch of double+ spaces
    summary = event.get('summary', '')
    normalized_event['message'] = re.sub('  +', '', summary).strip()

    normalized_event['location'] = event.get('location', '')
    normalized_event['description'] = event.get('description', '')
    normalized_event['htmlLink'] = event.get('htmlLink', '')
    normalized_event['all_day'] = 'date' in event['start']

    return normalized_event


def filter_events(events, **filters):
    """Filter a list of events by given filters."""
    filtered_events = []

    start_day = filters['start'].date()
    end_day = filters['end'].date()
    max_events = filters[CONF_MAXIMUM]

    for event in events:
        is_between = start_day <= event['dt_start'].date() <= end_day
        if (is_between and len(filtered_events) < max_events):
            filtered_events.append(event)

    return filtered_events


@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required(CONF_TYPE): 'calendar/events',
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_MAXIMUM, default=14): cv.positive_int,
    vol.Optional('start', default=datetime.min): vol.Any(None, cv.datetime),
    vol.Optional('end', default=datetime.max): vol.Any(None, cv.datetime),
})
async def get_calendar_info(hass: HomeAssistantType,
                            connection: websocket_api.ActiveConnection,
                            msg: Dict):
    """Handle calendar request."""
    component = hass.data[DOMAIN]
    calendar = component.get_entity(msg['entity_id'])

    if calendar is None:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'entity_not_found', 'Entity not found'))
        return

    if calendar.events is None:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'not_found', 'Events not found'))
        return

    filtered_events = filter_events(calendar.events, **msg)
    connection.send_message(
        websocket_api.result_message(msg['id'], filtered_events))


class CalendarEventDevice(Entity):
    """A calendar event device."""

    # Classes overloading this must set data to an object
    # with an update() method
    data = None

    def __init__(self, hass, data):
        """Create the Calendar Event Device."""
        self._name = data.get(CONF_NAME)
        self.dev_id = data.get(CONF_DEVICE_ID)
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, self.dev_id, hass=hass)

        self._cal_data = {
            'all_day': False,
            'message': '',
            'start': None,
            'end': None,
            'location': '',
            'description': '',
        }

        self._events = None
        self.update()

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def events(self):
        """Return all events of the entity."""
        return self._events

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {
            'message': self._cal_data.get('message', ''),
            'all_day': self._cal_data.get('all_day', False),
            'start_time': self._cal_data.get('start', None),
            'end_time': self._cal_data.get('end', None),
            'location': self._cal_data.get('location', None),
            'description': self._cal_data.get('description', None),
        }

    @property
    def state(self):
        """Return the state of the calendar event."""
        start = self._cal_data.get('dt_start', None)
        end = self._cal_data.get('dt_end', None)
        if start is None or end is None:
            return STATE_OFF

        now = dt.now()

        if start <= now < end:
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

        self._events = None

    def update(self):
        """Search for the next event."""
        if not self.data or not self.data.update():
            # update cached, don't do anything
            return

        if not self.data.event:
            # we have no event to work on, make sure we're clean
            self.cleanup()
        else:
            self._cal_data = normalize_event(self.data.event)

        if hasattr(self.data, 'events') and self.data.events:
            self._events = [normalize_event(event)
                            for event in self.data.events]


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
