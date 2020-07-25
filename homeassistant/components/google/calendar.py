"""Google Calendar."""
from datetime import timedelta
import logging
import math
from typing import Dict, Optional

from homeassistant.components.calendar.calendar import (
    CalendarEntity,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle, dt

from .api import GoogleAPI
from .const import DOMAIN, SERVICE_CALENDAR_DISCOVERY

_LOGGER = logging.getLogger(__name__)

CALENDAR_SYNC_TIME = timedelta(minutes=15)
CONTACTS_SYNC_TIME = timedelta(hours=12)

"""
Templates
{% for calendar in states.calendar -%}
{{ calendar.name }}
{% endfor %}


{% for event in states.calendar.contacts.attributes.schedule -%}
{{ event.start.strftime('%Y-%m-%d') }} {{ event.title }}
{% endfor %}


{% for event in states.calendar.contacts_calendar.attributes.schedule %}
{{ event.title }}
{% endfor %}
"""


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> bool:
    """Setup entry."""
    await async_register_services(hass, entry, async_add_entities)
    await async_register_webhooks(hass, entry, async_add_entities)

    # Discover calendars.
    if hass.services.has_service(
        DOMAIN, SERVICE_CALENDAR_DISCOVERY
    ) and not await hass.services.async_call(
        DOMAIN, SERVICE_CALENDAR_DISCOVERY, blocking=True
    ):
        _LOGGER.error(
            "Unable to discover calendars.  Try calling the `{domain}.{service}` service manually.".format(
                domain=DOMAIN, service=SERVICE_CALENDAR_DISCOVERY,
            )
        )

    return True


async def async_register_services(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Register services"""
    google = hass.data[DOMAIN][entry.entry_id]

    def discover_calendars(call):
        """Discover and register calendars"""
        calendars = []
        if google.calendar:
            # Discover and register Google Calendar calendars.
            for calendar in google.calendar.list_calendars():
                data = CalendarData(
                    google.calendar, calendar.get("id"), calendar.get("summary")
                )
                calendars.append(GoogleCalendarEntity(data))

        if google.people:
            # Register a Google Contacts calendar.
            data = ContactsCalendarData(
                google.people, entry.entry_id, "Contacts Calendar"
            )
            calendars.append(GoogleCalendarEntity(data))

        return async_add_entities(calendars, True)

    hass.services.async_register(DOMAIN, SERVICE_CALENDAR_DISCOVERY, discover_calendars)


async def async_register_webhooks(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Register webhooks"""
    # TODO: Register webhook for push updates.


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entry."""
    await hass.services.async_remove(DOMAIN, SERVICE_CALENDAR_DISCOVERY)
    # TODO: Unload webhook
    return True


class GoogleCalendarEntity(CalendarEntity):
    """Google Calendar Entity"""

    def update(self) -> None:
        """Update Google Calendar Entity"""
        self._data.update()
        self._events = self._data.events
        super().update()

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._data.calendar_id

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return self._data.name

    @property
    def should_poll(self) -> bool:
        """No need to poll. Calendar is updated via webhook."""
        # TODO: Change to false once push has been implemented.
        return True

    async def async_added_to_hass(self) -> bool:
        """When entity is added to hass."""
        # TODO: Subscribe to updates webhook and set callback listener
        return True


class CalendarData:
    """Calendar data"""

    def __init__(self, api: GoogleAPI, id: str, name: str):
        """Initialize calendar data."""
        self._api = api
        self.calendar_id = id
        self.name = name
        self.events = []

    @Throttle(CALENDAR_SYNC_TIME)
    def update(self):
        """Update calendar data"""
        self.events = []
        events = self._api.list_events(calendar_id=self.calendar_id)

        for event in events:
            self.events.append(GoogleCalendarEvent(event))


class ContactsCalendarData:
    """Contacts calendar data"""

    def __init__(self, api: GoogleAPI, id: str, name: str):
        """Initialize contacts calendar data."""
        self._api = api
        self.calendar_id = id
        self.name = name
        self.events = []

    @Throttle(CONTACTS_SYNC_TIME)
    def update(self):
        """Update contacts calendar data"""
        self.events = []
        contacts = self._api.list_contacts()

        for contact in contacts:
            contact_events = []
            names = contact.get("names", [])
            if not names:
                continue

            contact_name = "{display_name} {family_name}".format(
                display_name=names[0].get("givenName"),
                family_name=names[0].get("familyName"),
            )

            for event in contact.get("birthdays", []):
                contact_events.append(
                    {
                        "contact_name": contact_name,
                        "event_type": "birthday",
                        "event_date": event.get("date"),
                    }
                )

            for event in contact.get("events", []):
                contact_events.append(
                    {
                        "contact_name": contact_name,
                        "event_type": event.get("formattedType"),
                        "event_date": event.get("date"),
                    }
                )

            for event in contact_events:
                self.events.append(GoogleContactCalendarEvent(event))


class GoogleCalendarEvent(CalendarEvent):
    """
    Calendar Event object
    https://developers.google.com/calendar/concepts/events-calendars#events
    """

    def __init__(self, event: Dict):
        self.id = event.get("id")
        self.title = event.get("summary")
        self.description = event.get("description")
        self.location = event.get("location")

        _start = event.get("start")
        self.start = dt.parse_datetime(_start.get("dateTime", ""))
        if self.start is None:
            self.start = dt.parse_datetime(_start.get("date", ""))

        _end = event.get("end")
        self.end = dt.parse_datetime(_end.get("dateTime", ""))
        if self.end is None:
            self.end = dt.parse_datetime(_end.get("date", ""))

        self.status = event.get("status")

        organizer = event.get("organizer")
        if organizer is not None:
            self.organizer = organizer.get("email")

        creator = event.get("creator")
        if creator is not None:
            self.creator = creator.get("email")
        self.create = dt.parse_datetime(event.get("created", ""))
        self.update = dt.parse_datetime(event.get("updated", ""))
        self.ical_uid = event.get("iCalUID")
        self.url = event.get("htmlLink")


class GoogleContactCalendarEvent(CalendarEvent):
    """
    Calendar Event object
    """

    def __init__(self, event: Dict):
        self.title = ""

        event_date = event.get("event_date", "")
        if not event_date:
            return

        if not event_date.get("year"):
            event_date["year"] = dt.now().year

        self.start = dt.as_utc(dt.now().replace(**event_date)) or None
        if not self.start:
            return
        self.start = self.start.replace(hour=0, minute=0, second=0, microsecond=0)
        self.end = self.start + timedelta(days=1) - timedelta(seconds=1)

        event_count = None
        if event_date.get("year"):
            event_count = math.trunc(abs((dt.now() - self.start).days) / 365.25)

        ordinal = lambda n: "%d%s" % (
            n,
            "tsnrhtdd"[(math.floor(n / 10) % 10 != 1) * (n % 10 < 4) * n % 10 :: 4],
        )

        title_parts = []
        title_parts.append(
            "{contact_name}'s".format(contact_name=event.get("contact_name"))
        )
        if event_count:
            title_parts.append("{event_count}".format(event_count=ordinal(event_count)))
        title_parts.append("{event_type}".format(event_type=event.get("event_type")))
        self.title = " ".join(title_parts)

