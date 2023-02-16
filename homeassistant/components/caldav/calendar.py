"""Support for WebDav Calendar."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import partial
import logging
import re

import caldav
import voluptuous as vol

from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    CalendarEntity,
    CalendarEvent,
    extract_offset,
    is_offset_reached,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle, dt

_LOGGER = logging.getLogger(__name__)

CONF_CALENDARS = "calendars"
CONF_CUSTOM_CALENDARS = "custom_calendars"
CONF_CALENDAR = "calendar"
CONF_SEARCH = "search"
CONF_DAYS = "days"

OFFSET = "!!"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        # pylint: disable=no-value-for-parameter
        vol.Required(CONF_URL): vol.Url(),
        vol.Optional(CONF_CALENDARS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
        vol.Optional(CONF_CUSTOM_CALENDARS, default=[]): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_CALENDAR): cv.string,
                        vol.Required(CONF_NAME): cv.string,
                        vol.Required(CONF_SEARCH): cv.string,
                    }
                )
            ],
        ),
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_DAYS, default=1): cv.positive_int,
    }
)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    disc_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the WebDav Calendar platform."""
    url = config[CONF_URL]
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    days = config[CONF_DAYS]

    client = caldav.DAVClient(
        url, None, username, password, ssl_verify_cert=config[CONF_VERIFY_SSL]
    )

    calendars = client.principal().calendars()

    calendar_devices = []
    for calendar in list(calendars):
        # If a calendar name was given in the configuration,
        # ignore all the others
        if config[CONF_CALENDARS] and calendar.name not in config[CONF_CALENDARS]:
            _LOGGER.debug("Ignoring calendar '%s'", calendar.name)
            continue

        # Create additional calendars based on custom filtering rules
        for cust_calendar in config[CONF_CUSTOM_CALENDARS]:
            # Check that the base calendar matches
            if cust_calendar[CONF_CALENDAR] != calendar.name:
                continue

            name = cust_calendar[CONF_NAME]
            device_id = f"{cust_calendar[CONF_CALENDAR]} {cust_calendar[CONF_NAME]}"
            entity_id = generate_entity_id(ENTITY_ID_FORMAT, device_id, hass=hass)
            calendar_devices.append(
                WebDavCalendarEntity(
                    name, calendar, entity_id, days, True, cust_calendar[CONF_SEARCH]
                )
            )

        # Create a default calendar if there was no custom one
        if not config[CONF_CUSTOM_CALENDARS]:
            name = calendar.name
            device_id = calendar.name
            entity_id = generate_entity_id(ENTITY_ID_FORMAT, device_id, hass=hass)
            calendar_devices.append(
                WebDavCalendarEntity(name, calendar, entity_id, days)
            )

    add_entities(calendar_devices, True)


class WebDavCalendarEntity(CalendarEntity):
    """A device for getting the next Task from a WebDav Calendar."""

    def __init__(self, name, calendar, entity_id, days, all_day=False, search=None):
        """Create the WebDav Calendar Event Device."""
        self.data = WebDavCalendarData(calendar, days, all_day, search)
        self.entity_id = entity_id
        self._event: CalendarEvent | None = None
        self._attr_name = name

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        return await self.data.async_get_events(hass, start_date, end_date)

    def update(self) -> None:
        """Update event data."""
        self.data.update()
        self._event = self.data.event
        self._attr_extra_state_attributes = {
            "offset_reached": is_offset_reached(
                self._event.start_datetime_local, self.data.offset
            )
            if self._event
            else False
        }


class WebDavCalendarData:
    """Class to utilize the calendar dav client object to get next event."""

    def __init__(self, calendar, days, include_all_day, search):
        """Set up how we are going to search the WebDav calendar."""
        self.calendar = calendar
        self.days = days
        self.include_all_day = include_all_day
        self.search = search
        self.event = None
        self.offset = None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        # Get event list from the current calendar
        vevent_list = await hass.async_add_executor_job(
            partial(
                self.calendar.search,
                start=start_date,
                end=end_date,
                event=True,
                expand=True,
            )
        )
        event_list = []
        for event in vevent_list:
            if not hasattr(event.instance, "vevent"):
                _LOGGER.warning("Skipped event with missing 'vevent' property")
                continue
            vevent = event.instance.vevent
            if not self.is_matching(vevent, self.search):
                continue
            event_list.append(
                CalendarEvent(
                    summary=self.get_attr_value(vevent, "summary") or "",
                    start=self.to_local(vevent.dtstart.value),
                    end=self.to_local(self.get_end_date(vevent)),
                    location=self.get_attr_value(vevent, "location"),
                    description=self.get_attr_value(vevent, "description"),
                )
            )

        return event_list

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data."""
        start_of_today = dt.start_of_local_day()
        start_of_tomorrow = dt.start_of_local_day() + timedelta(days=self.days)

        # We have to retrieve the results for the whole day as the server
        # won't return events that have already started
        results = self.calendar.search(
            start=start_of_today,
            end=start_of_tomorrow,
            event=True,
            expand=True,
        )

        # Create new events for each recurrence of an event that happens today.
        # For recurring events, some servers return the original event with recurrence rules
        # and they would not be properly parsed using their original start/end dates.
        new_events = []
        for event in results:
            if not hasattr(event.instance, "vevent"):
                _LOGGER.warning("Skipped event with missing 'vevent' property")
                continue
            vevent = event.instance.vevent
            for start_dt in vevent.getrruleset() or []:
                _start_of_today = start_of_today
                _start_of_tomorrow = start_of_tomorrow
                if self.is_all_day(vevent):
                    start_dt = start_dt.date()
                    _start_of_today = _start_of_today.date()
                    _start_of_tomorrow = _start_of_tomorrow.date()
                if _start_of_today <= start_dt < _start_of_tomorrow:
                    new_event = event.copy()
                    new_vevent = new_event.instance.vevent
                    if hasattr(new_vevent, "dtend"):
                        dur = new_vevent.dtend.value - new_vevent.dtstart.value
                        new_vevent.dtend.value = start_dt + dur
                    new_vevent.dtstart.value = start_dt
                    new_events.append(new_event)
                elif _start_of_tomorrow <= start_dt:
                    break
        vevents = [
            event.instance.vevent
            for event in results + new_events
            if hasattr(event.instance, "vevent")
        ]

        # dtstart can be a date or datetime depending if the event lasts a
        # whole day. Convert everything to datetime to be able to sort it
        vevents.sort(key=lambda x: self.to_datetime(x.dtstart.value))

        vevent = next(
            (
                vevent
                for vevent in vevents
                if (
                    self.is_matching(vevent, self.search)
                    and (not self.is_all_day(vevent) or self.include_all_day)
                    and not self.is_over(vevent)
                )
            ),
            None,
        )

        # If no matching event could be found
        if vevent is None:
            _LOGGER.debug(
                "No matching event found in the %d results for %s",
                len(vevents),
                self.calendar.name,
            )
            self.event = None
            return

        # Populate the entity attributes with the event values
        (summary, offset) = extract_offset(
            self.get_attr_value(vevent, "summary") or "", OFFSET
        )
        self.event = CalendarEvent(
            summary=summary,
            start=self.to_local(vevent.dtstart.value),
            end=self.to_local(self.get_end_date(vevent)),
            location=self.get_attr_value(vevent, "location"),
            description=self.get_attr_value(vevent, "description"),
        )
        self.offset = offset

    @staticmethod
    def is_matching(vevent, search):
        """Return if the event matches the filter criteria."""
        if search is None:
            return True

        pattern = re.compile(search)
        return (
            hasattr(vevent, "summary")
            and pattern.match(vevent.summary.value)
            or hasattr(vevent, "location")
            and pattern.match(vevent.location.value)
            or hasattr(vevent, "description")
            and pattern.match(vevent.description.value)
        )

    @staticmethod
    def is_all_day(vevent):
        """Return if the event last the whole day."""
        return not isinstance(vevent.dtstart.value, datetime)

    @staticmethod
    def is_over(vevent):
        """Return if the event is over."""
        return dt.now() >= WebDavCalendarData.to_datetime(
            WebDavCalendarData.get_end_date(vevent)
        )

    @staticmethod
    def to_datetime(obj):
        """Return a datetime."""
        if isinstance(obj, datetime):
            return WebDavCalendarData.to_local(obj)
        return dt.dt.datetime.combine(obj, dt.dt.time.min).replace(
            tzinfo=dt.DEFAULT_TIME_ZONE
        )

    @staticmethod
    def to_local(obj: datetime | date) -> datetime | date:
        """Return a datetime as a local datetime, leaving dates unchanged.

        This handles giving floating times a timezone for comparison
        with all day events and dropping the custom timezone object
        used by the caldav client and dateutil so the datetime can be copied.
        """
        if isinstance(obj, datetime):
            return dt.as_local(obj)
        return obj

    @staticmethod
    def get_attr_value(obj, attribute):
        """Return the value of the attribute if defined."""
        if hasattr(obj, attribute):
            return getattr(obj, attribute).value
        return None

    @staticmethod
    def get_end_date(obj):
        """Return the end datetime as determined by dtend or duration."""
        if hasattr(obj, "dtend"):
            enddate = obj.dtend.value

        elif hasattr(obj, "duration"):
            enddate = obj.dtstart.value + obj.duration.value

        else:
            enddate = obj.dtstart.value + timedelta(days=1)

        return enddate
