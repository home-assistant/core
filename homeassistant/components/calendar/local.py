"""Component to manage a calendar."""
import asyncio
import logging

from homeassistant.components import http
from homeassistant.components.calendar import DOMAIN

SUBDOMAIN = 'local'
DEPENDENCIES = ['http']
_LOGGER = logging.getLogger(__name__)
EVENT = 'calendar_updated'


@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Initialize the calendar."""

    hass.http.register_view(CalendarView)
    hass.http.register_view(CalendarListView)

    yield from hass.components.frontend.async_register_built_in_panel(
        'calendar', 'calendar', 'mdi:calendar')

    return True


class CalendarView(http.HomeAssistantView):
    """View to retrieve calendar content."""

    url = '/api/calendar'
    name = "api:calendar"
    extra_urls = ['/api/calendar/']

    async def post(self, request):
        """Retrieve calendar items."""
        data = await request.json()
        if data.get("calendars"):
            ret = []
            for calendar_name in data.get("calendars"):
                if calendar_name in request.app['hass'].data[DOMAIN]:
                    ret.extend(request.app['hass'].data[DOMAIN][calendar_name].items)
            return self.json(ret)
        return self.json([])


class CalendarListView(http.HomeAssistantView):
    """View to retrieve calendar list."""

    url = '/api/calendar-list'
    name = "api:calendar-list"

    async def get(self, request):
        """Retrieve calendar list."""
        calendar_list = []
        for calendar, eventdata in request.app['hass'].data[DOMAIN].items():
            cal = {"name": calendar, "color": None}
            if eventdata.items:
                cal['color'] = eventdata.items[0].get('color')

            calendar_list.append(cal)
        calendar_list.sort(key=lambda x: x['name'])

        return self.json(calendar_list)
