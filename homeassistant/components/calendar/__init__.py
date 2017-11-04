"""
Support for Google Calendar event device sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/calendar/
"""
import asyncio
import logging
from datetime import timedelta

from aiohttp.web_exceptions import HTTPNotFound


import homeassistant.util.dt as dt

from homeassistant.helpers import config_per_platform, discovery
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.components.http import HomeAssistantView
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_prepare_setup_platform

from homeassistant.const import STATE_OFF, STATE_ON

DEPENDENCIES = ['http']
DOMAIN = 'calendar'
SCAN_INTERVAL = timedelta(seconds=10)
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for calendars."""
    calendars = []

    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    hass.components.frontend.register_built_in_panel(
        'calendar', 'Calendar', 'mdi:calendar')
    hass.http.register_view(CalendarPlatformsView(calendars))
    hass.http.register_view(CalendarEventView(calendars))

    @asyncio.coroutine
    def async_setup_platform(p_type, p_config=None, discovery_info=None):
        """Set up a calendar platform."""
        platform = yield from async_prepare_setup_platform(
            hass, config, DOMAIN, p_type)

        if platform is None:
            _LOGGER.error("Unknown calendar platform specified")
            return

        _LOGGER.info("Setting up %s.%s", DOMAIN, p_type)
        calendar = None
        try:
            if hasattr(platform, 'async_get_handler'):
                calendar = yield from platform.async_get_handler(
                    hass, p_config, discovery_info)
            elif hasattr(platform, 'get_handler'):
                calendar = yield from hass.async_add_job(
                    platform.get_handler, hass, p_config, discovery_info)
            else:
                raise HomeAssistantError("Invalid calendar platform.")

            if calendar is None:
                _LOGGER.error(
                    "Failed to initialize calendar platform %s", p_type)
                return

        except Exception:
            _LOGGER.exception("Error setting up platform %s", p_type)
            return

        calendars.extend(calendar)
        yield from component.async_add_entities(calendar)

    setup_tasks = [async_setup_platform(p_type, p_config) for p_type, p_config
                   in config_per_platform(config, DOMAIN)]

    if setup_tasks:
        yield from asyncio.wait(setup_tasks, loop=hass.loop)

    @asyncio.coroutine
    def async_platform_discovered(platform, info):
        """Setup discovered platform."""
        yield from async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    return True


class Calendar(Entity):
    """Entity for each calendar platform."""

    def __init__(self, hass, name):
        """Initialze calendar entity."""
        self.hass = hass
        self._name = name

        self._next_event = None

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @asyncio.coroutine
    def async_get_events(self):
        """Return a list of events."""
        raise NotImplementedError()

    @property
    def state(self):
        """Return the state of the calendar."""
        if self._next_event is None:
            return STATE_OFF

        if self._next_event.is_active():
            return STATE_ON

        return STATE_OFF


class CalendarEvent(object):
    """Representation of an event."""

    def __init__(self, start, end, text):
        """Initialize the event."""
        self._start = start
        self._end = end
        self._text = text

    @property
    def start(self):
        """Return start time set on the event."""
        return self._start

    @property
    def end(self):
        """Return end time set on the event."""
        return self._end

    @property
    def text(self):
        """Return text set on the event."""
        return self._text

    def is_active(self):
        """Check whether event is currently active."""
        if self._start is None:
            return False

        if self._end is None:
            return False

        now = dt.now()

        if self._start <= now and self._end > now:
            return True

        return False


class CalendarView(HomeAssistantView):
    """Base Calendar view."""

    def __init__(self, calendars):
        """Initialize base calendar view."""
        self.calendars = calendars

    def get_calendar(self, platform):
        """Get calendar by name."""
        for calendar in self.calendars:
            if calendar.name == platform:
                return calendar
        return HTTPNotFound


class CalendarPlatformsView(CalendarView):
    """All platforms view."""

    url = "/api/calendar/platforms"
    name = "api:calendar:platforms"

    @asyncio.coroutine
    def get(self, request):
        """Get all calendars."""
        platforms = []
        for calendar in self.calendars:
            platforms.append(calendar.name)
        return self.json(platforms)


class CalendarEventView(CalendarView):
    """Events per platform view."""

    url = "/api/calendar/events/{platform}"
    name = "api:calendar:events"

    @asyncio.coroutine
    def get(self, request, platform):
        """Get all events for platform."""
        calendar = self.get_calendar(platform)
        events = yield from calendar.async_get_events()
        return self.json(events)
