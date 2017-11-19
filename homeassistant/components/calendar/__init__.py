"""
Support for Google Calendar event device sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/calendar/
"""
import asyncio
import logging
from datetime import timedelta

from aiohttp.web_exceptions import HTTPNotFound

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util import dt
from homeassistant.components.http import HomeAssistantView


DEPENDENCIES = ['http']


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'calendar'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SCAN_INTERVAL = timedelta(seconds=60)


@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for calendars."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    hass.components.frontend.register_built_in_panel(
        'calendar', 'Calendar', 'mdi:calendar')
    hass.http.register_view(CalendarPlatformsView(component))
    hass.http.register_view(CalendarEventView(component))

    yield from component.async_setup(config)
    return True


class Calendar(Entity):
    """Entity for each calendar platform."""

    @asyncio.coroutine
    def async_get_events(self):
        """Return a list of events."""
        raise NotImplementedError()

    def update_next_event(self):
        """Find next occuring event in all events."""
        return next((event for event in self._events if
                    event.start > dt.now() or
                    (event.start < dt.now() and
                     event.end > dt.now())), None)

    @property
    def next_event(self):
        """Return next occuring event."""
        return None

    @property
    def state(self):
        """Return the state of the calendar."""
        if self.next_event is None:
            return STATE_OFF

        if self.next_event.is_active():
            return STATE_ON

        return STATE_OFF


class CalendarEvent(object):
    """Representation of an event."""

    @property
    def start(self):
        """Return start time set on the event."""
        return None

    @property
    def end(self):
        """Return end time set on the event."""
        return None

    @property
    def message(self):
        """Return text set on the event."""
        return None

    @property
    def location(self):
        """Return location of the event."""
        return None

    @property
    def labels(self):
        """Return labels of the event."""
        return None

    def is_active(self):
        """Check whether event is currently active."""
        if self.start is None:
            return False

        if self.end is None:
            return False

        now = dt.now()

        if self.start <= now and self.end > now:
            return True

        return False

    def as_dict(self):
        """Return response in a dict."""
        event = {
            'start': self.start,
            'end': self.end,
            'message': self.message
        }

        if self.location is not None:
            event['location'] = self.location

        if self.labels is not None:
            event['labels'] = self.labels

        return event


class CalendarView(HomeAssistantView):
    """Base Calendar view."""

    def __init__(self, component):
        """Initialize base calendar view."""
        self._component = component

    def get_calendar(self, platform):
        """Get calendar by name."""
        for calendar in self._component.entities.values():
            if calendar.name == platform:
                return calendar
        return None


class CalendarPlatformsView(CalendarView):
    """All platforms view."""

    url = "/api/calendar/platforms"
    name = "api:calendar:platforms"

    @asyncio.coroutine
    def get(self, request):
        """Get all calendars."""
        for calendar in self._component.entities.values():
            _LOGGER.debug('Entity: %s', calendar.name)

        return self.json([calendar.name for calendar in
                          self._component.entities.values()])


class CalendarEventView(CalendarView):
    """Events per platform view."""

    url = "/api/calendar/events/{platform}"
    name = "api:calendar:events"

    @asyncio.coroutine
    def get(self, request, platform):
        """Get all events for platform."""
        calendar = self.get_calendar(platform)
        if calendar is None:
            return HTTPNotFound
        events = yield from calendar.async_get_events()
        return self.json(events)
