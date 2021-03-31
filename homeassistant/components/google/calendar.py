"""Support for Google Calendar Search binary sensors."""
import copy
from datetime import timedelta
import logging

from httplib2 import ServerNotFoundError

from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT,
    CalendarEventDevice,
    calculate_offset,
    is_offset_reached,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_ENTITIES, CONF_NAME, CONF_OFFSET
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.util import Throttle, dt

from . import (
    CONF_CAL_ID,
    CONF_IGNORE_AVAILABILITY,
    CONF_MAX_RESULTS,
    CONF_SEARCH,
    CONF_TRACK,
    DEFAULT_CONF_OFFSET,
    TOKEN_FILE,
    GoogleCalendarService,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_GOOGLE_SEARCH_PARAMS = {
    "orderBy": "startTime",
    "maxResults": 100,
    "singleEvents": True,
}

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


def setup_platform(hass, config, add_entities, disc_info=None):
    """Set up the calendar platform for event devices."""
    if disc_info is None:
        return

    if not any(data[CONF_TRACK] for data in disc_info[CONF_ENTITIES]):
        return

    calendar_service = GoogleCalendarService(hass.config.path(TOKEN_FILE))
    entities = []
    for data in disc_info[CONF_ENTITIES]:
        if not data[CONF_TRACK]:
            continue
        entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, data[CONF_DEVICE_ID], hass=hass
        )
        entity = GoogleCalendarEventDevice(
            calendar_service, disc_info[CONF_CAL_ID], data, entity_id
        )
        entities.append(entity)

    add_entities(entities, True)


class GoogleCalendarEventDevice(CalendarEventDevice):
    """A calendar event device."""

    def __init__(self, calendar_service, calendar, data, entity_id):
        """Create the Calendar event device."""
        self.data = GoogleCalendarData(
            calendar_service,
            calendar,
            data.get(CONF_SEARCH),
            data.get(CONF_IGNORE_AVAILABILITY),
            data.get(CONF_MAX_RESULTS),
        )
        self._event = None
        self._name = data[CONF_NAME]
        self._offset = data.get(CONF_OFFSET, DEFAULT_CONF_OFFSET)
        self._offset_reached = False
        self.entity_id = entity_id

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return {"offset_reached": self._offset_reached}

    @property
    def event(self):
        """Return the next upcoming event."""
        return self._event

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        return await self.data.async_get_events(hass, start_date, end_date)

    def update(self):
        """Update event data."""
        self.data.update()
        event = copy.deepcopy(self.data.event)
        if event is None:
            self._event = event
            return
        event = calculate_offset(event, self._offset)
        self._offset_reached = is_offset_reached(event)
        self._event = event


class GoogleCalendarData:
    """Class to utilize calendar service object to get next event."""

    def __init__(
        self, calendar_service, calendar_id, search, ignore_availability, max_results
    ):
        """Set up how we are going to search the google calendar."""
        self.calendar_service = calendar_service
        self.calendar_id = calendar_id
        self.search = search
        self.ignore_availability = ignore_availability
        self.max_results = max_results
        self.event = None

    def _prepare_query(self):
        try:
            service = self.calendar_service.get()
        except ServerNotFoundError:
            _LOGGER.error("Unable to connect to Google")
            return None, None
        params = dict(DEFAULT_GOOGLE_SEARCH_PARAMS)
        params["calendarId"] = self.calendar_id
        if self.max_results:
            params["maxResults"] = self.max_results
        if self.search:
            params["q"] = self.search

        return service, params

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        service, params = await hass.async_add_executor_job(self._prepare_query)
        if service is None:
            return []
        params["timeMin"] = start_date.isoformat("T")
        params["timeMax"] = end_date.isoformat("T")

        events = await hass.async_add_executor_job(service.events)
        result = await hass.async_add_executor_job(events.list(**params).execute)

        items = result.get("items", [])
        event_list = []
        for item in items:
            if not self.ignore_availability and "transparency" in item:
                if item["transparency"] == "opaque":
                    event_list.append(item)
            else:
                event_list.append(item)
        return event_list

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data."""
        service, params = self._prepare_query()
        if service is None:
            return
        params["timeMin"] = dt.now().isoformat("T")

        events = service.events()
        result = events.list(**params).execute()

        items = result.get("items", [])

        new_event = None
        for item in items:
            if not self.ignore_availability and "transparency" in item:
                if item["transparency"] == "opaque":
                    new_event = item
                    break
            else:
                new_event = item
                break

        self.event = new_event
