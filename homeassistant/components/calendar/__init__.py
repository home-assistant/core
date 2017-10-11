"""
Support for Google Calendar event device sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/calendar/
"""
import asyncio
import logging
from datetime import timedelta

from aiohttp.web_exceptions import HTTPNotFound

from homeassistant.helpers import config_per_platform, discovery
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.components.http import HomeAssistantView
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_prepare_setup_platform

DEPENDENCIES = ['http']
DOMAIN = 'calendar'
SCAN_INTERVAL = timedelta(seconds=10)
_LOGGER = logging.getLogger(__name__)

@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for calendars."""
    calendars = []

    component = EntityComponent(
            _LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    hass.components.frontend.register_built_in_panel(
        'calendar', 'Calendar', 'mdi:calendar')
    hass.http.register_view(CalendarPlatformsView(calendars))
    hass.http.register_view(CalendarEventView(calendars))

    @asyncio.coroutine
    def async_setup_platform(p_type, p_config={}, discovery_info={}):
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
                calendar = yield from platform.async_get_handler(hass, p_config, discovery_info)
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

        calendars.append(calendar)

    setup_tasks = [async_setup_platform(p_type, p_config) for p_type, p_config
                   in config_per_platform(config, DOMAIN)]

    if setup_tasks:
        yield from asyncio.wait(setup_tasks, loop=hass.loop)
        yield from component.async_add_entities(calendars)
    return True

class Calendar(Entity):
    """Entity for each calendar platform."""
    def __init__(self, hass, name):
        """Initialze calendar entity."""
        self.hass = hass
        self._name = name

    @property
    def state(self):
        """Return the status of the calendar."""
        return 'state' # TODO

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @asyncio.coroutine
    def async_get_events(self):
        """Returns a list of events."""
        raise NotImplementedError()

class CalendarView(HomeAssistantView):
    """Base Calendar view."""
    def __init__(self, calendars):
        self.calendars = calendars

    def get_calendar(self, platform):
        for calendar in self.calendars:
            if calendar.name == platform:
                return calendar
        return HTTPNotFound

class CalendarPlatformsView(CalendarView):

    url = "/api/calendar/platforms"
    name = "api:calendar:platforms"

    @asyncio.coroutine
    def get(self, request):
        platforms = []
        for calendar in self.calendars:
            platforms.append(calendar.name)
        return self.json(platforms)

class CalendarEventView(CalendarView):
    url = "/api/calendar/events/{platform}"
    name = "api:calendar:events"

    @asyncio.coroutine
    def get(self, request, platform):
        calendar = self.get_calendar(platform)
        events = yield from calendar.async_get_events()
        return self.json(events)