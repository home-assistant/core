"""Support for Google Calendar Search binary sensors."""
from datetime import timedelta
import logging

from homeassistant.components.calendar import CalendarEventDevice
from homeassistant.util import Throttle, dt

from . import (
    CONF_CAL_ID, CONF_ENTITIES, CONF_IGNORE_AVAILABILITY, CONF_SEARCH,
    CONF_TRACK, TOKEN_FILE, CONF_MAX_RESULTS, GoogleCalendarService)

_LOGGER = logging.getLogger(__name__)

DEFAULT_GOOGLE_SEARCH_PARAMS = {
    'orderBy': 'startTime',
    'maxResults': 5,
    'singleEvents': True,
}

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


def setup_platform(hass, config, add_entities, disc_info=None):
    """Set up the calendar platform for event devices."""
    if disc_info is None:
        return

    if not any(data[CONF_TRACK] for data in disc_info[CONF_ENTITIES]):
        return

    calendar_service = GoogleCalendarService(hass.config.path(TOKEN_FILE))
    add_entities([GoogleCalendarEventDevice(hass, calendar_service,
                                            disc_info[CONF_CAL_ID], data)
                  for data in disc_info[CONF_ENTITIES] if data[CONF_TRACK]])


class GoogleCalendarEventDevice(CalendarEventDevice):
    """A calendar event device."""

    def __init__(self, hass, calendar_service, calendar, data):
        """Create the Calendar event device."""
        self.data = GoogleCalendarData(calendar_service, calendar,
                                       data.get(CONF_SEARCH),
                                       data.get(CONF_IGNORE_AVAILABILITY),
                                       data.get(CONF_MAX_RESULTS))

        super().__init__(hass, data)

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        return await self.data.async_get_events(hass, start_date, end_date)


class GoogleCalendarData:
    """Class to utilize calendar service object to get next event."""

    def __init__(self, calendar_service, calendar_id, search,
                 ignore_availability, max_results):
        """Set up how we are going to search the google calendar."""
        self.calendar_service = calendar_service
        self.calendar_id = calendar_id
        self.search = search
        self.ignore_availability = ignore_availability
        self.max_results = max_results
        self.event = None

    def _prepare_query(self):
        # pylint: disable=import-error
        from httplib2 import ServerNotFoundError

        try:
            service = self.calendar_service.get()
        except ServerNotFoundError:
            _LOGGER.warning("Unable to connect to Google, using cached data")
            return False
        params = dict(DEFAULT_GOOGLE_SEARCH_PARAMS)
        params['calendarId'] = self.calendar_id
        if self.max_results:
            params['max_results'] = self.max_results
        if self.search:
            params['q'] = self.search

        return service, params

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        service, params = await hass.async_add_job(self._prepare_query)
        params['timeMin'] = start_date.isoformat('T')
        params['timeMax'] = end_date.isoformat('T')

        events = await hass.async_add_job(service.events)
        result = await hass.async_add_job(events.list(**params).execute)

        items = result.get('items', [])
        event_list = []
        for item in items:
            if (not self.ignore_availability
                    and 'transparency' in item.keys()):
                if item['transparency'] == 'opaque':
                    event_list.append(item)
            else:
                event_list.append(item)
        return event_list

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data."""
        service, params = self._prepare_query()
        params['timeMin'] = dt.now().isoformat('T')

        events = service.events()
        result = events.list(**params).execute()

        items = result.get('items', [])

        new_event = None
        for item in items:
            if (not self.ignore_availability
                    and 'transparency' in item.keys()):
                if item['transparency'] == 'opaque':
                    new_event = item
                    break
            else:
                new_event = item
                break

        self.event = new_event
        return True
