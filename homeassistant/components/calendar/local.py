"""Component to manage a calendar."""
import asyncio
import logging

from homeassistant.components import http

SUBDOMAIN = 'local'
DEPENDENCIES = ['http']
_LOGGER = logging.getLogger(__name__)
EVENT = 'calendar_updated'


@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Initialize the calendar."""
    hass.http.register_view(CalendarListView)

    yield from hass.components.frontend.async_register_built_in_panel(
        'calendar', 'calendar', 'mdi:calendar')

    return True


class CalendarListView(http.HomeAssistantView):
    """View to retrieve calendar list."""

    url = '/api/calendars'
    name = "api:calendars"

    async def get(self, request):
        """Retrieve calendar list."""
        entity_ids = [e for e in request.app['hass'].states.async_entity_ids()
                      if e.startswith('calendar.')]
        calendar_list = []
        for entity_id in entity_ids:
            entity = request.app['hass'].states.get(entity_id)
            entity_short_name = entity.entity_id.split('.', 1)[-1]
            cal = {"name": entity.attributes.get('friendly_name'),
                   "color": entity.attributes.get('color'),
                   "entity_id": entity_short_name}
            calendar_list.append(cal)

        calendar_list.sort(key=lambda x: x['name'])

        return self.json(calendar_list)
