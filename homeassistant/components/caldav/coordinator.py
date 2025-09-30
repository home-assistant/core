"""Data update coordinator for caldav."""

from __future__ import annotations

import contextlib
import copy
from datetime import date, datetime, time, timedelta
from functools import partial
import logging
import re
from typing import TYPE_CHECKING, Any, Literal, TypeVar

import caldav
from caldav import CalendarObjectResource
from caldav.lib.error import NotFoundError
import dateutil
from dateutil.rrule import rrulestr
import icalendar
import voluptuous as vol

from homeassistant.components.calendar import VALID_FREQS, CalendarEvent, extract_offset
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import get_attr_value
from .const import DEFAULT_SCAN_INTERVAL

_CC = TypeVar("_CC", bound="CalendarObjectResource")

if TYPE_CHECKING:
    from . import CalDavConfigEntry

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)
OFFSET = "!!"


class CalDavUpdateCoordinator(DataUpdateCoordinator[CalendarEvent | None]):
    """Class to utilize the calendar dav client object to get next event."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: CalDavConfigEntry | None,
        calendar: caldav.Calendar,
        days: int,
        include_all_day: bool,
        search: str | None,
    ) -> None:
        """Set up how we are going to search the WebDav calendar."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"CalDAV {calendar.name}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                if entry
                else DEFAULT_SCAN_INTERVAL
            ),
        )
        self.calendar = calendar
        self.days = days
        self.include_all_day = include_all_day
        self.search = search
        self.offset: timedelta | None = None

    async def async_get_event(
        self, hass: HomeAssistant, uid: str
    ) -> caldav.Event | None:
        """Get a single event by its unique identifier."""
        try:
            event = await hass.async_add_executor_job(self.calendar.event_by_uid, uid)
        except NotFoundError:
            _LOGGER.debug("No event found with uid=%s", uid)
            return None
        if event is None or not hasattr(event.instance, "vevent"):
            return None
        assert isinstance(event, caldav.Event)
        return event

    async def async_get_event_recurrence(
        self, hass: HomeAssistant, uid: str, recurrence_id: str | None = None
    ) -> caldav.Event | None:
        """Get a single event by its unique identifier and recurrence id."""
        if not recurrence_id:
            return await self.async_get_event(hass, uid)

        d = self.parse_recurrence_id(recurrence_id)

        event_list_from_server = await hass.async_add_executor_job(
            partial(
                self.calendar.search,
                uid=uid,
                start=d,
                end=d + timedelta(seconds=1),
                event=True,
                expand=True,
            )
        )

        # Unfortunately, event_list_from_server may contain more than one object.
        # As of 28.09.2025, Nextcloud seems to ignore the UID filter when specifying a search interval.
        # So we have to search for the UID manually.
        event_list = []
        for event in event_list_from_server:
            if not hasattr(event.instance, "vevent"):
                _LOGGER.warning("Skipped event with missing 'vevent' property")
                continue
            vevent = event.instance.vevent
            if not self.is_matching(vevent, self.search):
                continue
            assert isinstance(event, caldav.Event)
            assert hasattr(event, "icalendar_component")  # for mypy
            # Skip if not the UID we're looking for
            if event.icalendar_component["uid"] != uid:
                continue
            event_list.append(event)

        if len(event_list) == 0:
            _LOGGER.error(
                "No event recurrences found with uid=%s and recurrence-id=%s",
                uid,
                recurrence_id,
            )
            return None

        event = event_list[0]

        if len(event_list) > 1:
            _LOGGER.warning(
                "More than one event recurrence found with uid=%s and recurrence-id=%s. Continuing with first event in list: %s",
                uid,
                recurrence_id,
                event,
            )

        return event

    # from core/homeassistant/components/calenda/__init__.py
    @staticmethod
    def _validate_rrule(value: Any) -> str:
        """Validate a recurrence rule string."""
        if value is None:
            raise vol.Invalid("rrule value is None")

        if not isinstance(value, str):
            raise vol.Invalid("rrule value expected a string")

        try:
            rrulestr(value)
        except ValueError as err:
            raise vol.Invalid(f"Invalid rrule '{value}': {err}") from err

        # Example format: FREQ=DAILY;UNTIL=...
        rule_parts = dict(s.split("=", 1) for s in value.split(";"))
        if not (freq := rule_parts.get("FREQ")):
            raise vol.Invalid("rrule did not contain FREQ")

        if freq not in VALID_FREQS:
            raise vol.Invalid(f"Invalid frequency for rule: {value}")

        return str(value)

    def vevent_to_hass_event(self, vevent) -> CalendarEvent:
        """Convert a VEVENT to a Home Assistant CalendarEvent."""
        # recurrence-id needs some special treatment
        recurrence_id = get_attr_value(vevent, "recurrence-id")
        if recurrence_id is not None:
            recurrence_id = str(recurrence_id)

        try:
            rrule = get_attr_value(vevent, "rrule")
            # Validate rrule if present
            if rrule is not None:
                self._validate_rrule(str(rrule))
        except vol.Invalid as err:
            _LOGGER.error(
                "Invalid rrule in event %s will be discarded: %s",
                get_attr_value(vevent, "uid"),
                err,
            )
            rrule = None

        return CalendarEvent(
            uid=get_attr_value(vevent, "uid"),
            recurrence_id=recurrence_id,
            rrule=rrule,
            summary=get_attr_value(vevent, "summary") or "",
            start=self.to_local(vevent.dtstart.value),
            end=self.to_local(self.get_end_date(vevent)),
            location=get_attr_value(vevent, "location"),
            description=get_attr_value(vevent, "description") or "",
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        _LOGGER.info(
            "Getting events between %s and %s from %s (%s)",
            start_date,
            end_date,
            self.calendar.name,
            self.calendar.url,
        )
        # Get event list from the current calendar
        vevent_list = await hass.async_add_executor_job(
            partial(
                self.search_calendar_events,  # use our own version that better handles recurring events
                start=start_date,
                end=end_date,
                event=True,
                expand="client",  # Recurring events should be expanded, see https://developers.home-assistant.io/docs/core/entity/calendar/#get-events
            )
        )

        # I see consistently hass complaining about a blocking call when executing `if not hasattr(event.instance, "vevent"):`
        # Therefore use the executor.
        def get_vevent_list() -> list[CalendarEvent]:
            event_list = []
            for event in vevent_list:
                if not hasattr(event.instance, "vevent"):
                    _LOGGER.warning("Skipped event with missing 'vevent' property")
                    continue
                vevent = event.instance.vevent
                if not self.is_matching(vevent, self.search):
                    continue

                event_list.append(self.vevent_to_hass_event(vevent))

            return event_list

        return await self.hass.async_add_executor_job(get_vevent_list)

    ################################################################################
    # The following code is mostly copied from caldav/collection.py to work around
    # some limitations in the caldav library (1.6.0).
    # It has been modified to better handle recurring events. Expanding recurring
    # events on the server side is not always possible, so we do it on the client
    # side.
    ################################################################################
    def search_calendar_events(
        self,
        expand: bool | Literal["server", "client"] = False,
        split_expanded: bool = True,
        include_completed: bool = False,
        **kwargs,
    ) -> list[_CC]:
        """Creates an XML query, does a REPORT request towards the server and returns objects found.

        It uses caldav.collection.search() to search for events.
        However, if expand="client" is requested, the recurrence properties
        of the master event are copied to the expanded recurrence events.
        If the master event has a rrule with COUNT, then the COUNT of the
        expanded evets will be decremented to indicate the number of remaining events.
        """

        objects = self.calendar.search(expand=(expand and expand == "server"), **kwargs)

        if expand and expand != "server":  # pylint: disable=too-many-nested-blocks
            ## expand can only be used together with start and end (and not
            ## with xml).  Error checking has already been done in
            ## build_search_xml_query above.
            start = kwargs["start"]
            end = kwargs["end"]

            ## Verify that any recurring objects returned are already expanded
            for o in objects:
                component = o.icalendar_component
                if component is None:
                    continue

                _LOGGER.debug("Processing event: %s", o.icalendar_instance)

                # Check for recurrence properties
                recurrence_properties = ["exdate", "exrule", "rdate", "rrule"]
                # Here starts our code: we need to collect all the recurrence property values
                recurrence_property_values = {}
                # Go through all recurrence properties and collect their values
                for key in recurrence_properties:
                    if key in component:
                        if key in ["exrule", "rdate"]:
                            _LOGGER.info(
                                "%s property found in calendar object. This is not fully supported and may lead to incorrect results",
                                key,
                            )
                        recurrence_property_values[key] = component[key]
                # Expand recurrence rule(s); next two line from caldav library
                if any(key in component for key in recurrence_properties):
                    o.expand_rrule(start, end, include_completed=include_completed)
                    # Our code from here...
                    # Create a rrule objectthat will help us to count the number of previous occurrences
                    rrule = None
                    master_count = None
                    if "rrule" in recurrence_property_values:
                        vrrule = recurrence_property_values["rrule"]
                        if "count" in vrrule:
                            # note: we don't have to consider exdates here because we want those dates to be counted.
                            # note2: this applies only to our use-case where we use ex-date to delete single occurrences.
                            master_count = vrrule["count"][0]
                            rrule = dateutil.rrule.rrulestr(
                                vrrule.to_ical().decode("utf-8"),
                                dtstart=icalendar.tools.to_datetime(
                                    o.icalendar_component["dtstart"].dt
                                ),
                            )

                    # Restore the recurrence properties
                    for sc in o.icalendar_instance.subcomponents:
                        if sc.name != "VEVENT":
                            continue
                        for key, value in recurrence_property_values.items():
                            sc[key] = copy.deepcopy(
                                value
                            )  # it is important here to make a copy of the original rrule because otherwise we can't edit it further down
                            if (
                                key == "rrule"
                                and rrule is not None
                                and master_count is not None
                            ):
                                # Special handling for RRULE with COUNT. We subtract the number of previous occurrences
                                # so that for the current occurrence only the number of remaining recurrences
                                # (including the current one) is displayed as COUNT.
                                # This mimics the behavior of Nextcloud, which I personally find preferable because
                                # this when editing number of recurrences in the home assistant UI we will get the
                                # expected behavior that changing the COUNT e.g. from 4 to 8 will result in 4 more recurrences (and not 8).
                                recurrences_up_to_now = rrule.between(
                                    after=icalendar.tools.to_datetime(
                                        o.icalendar_component["dtstart"].dt
                                    ),
                                    before=icalendar.tools.to_datetime(
                                        sc["dtstart"].dt
                                    ),
                                    inc=True,
                                )
                                if len(recurrences_up_to_now) > 0:
                                    sc["rrule"]["count"] = [
                                        master_count - (len(recurrences_up_to_now) - 1)
                                    ]

            ## An expanded recurring object comes as one Event() with
            ## icalendar data containing multiple objects.  The caller may
            ## expect multiple Event()s.  This code splits events into
            ## separate objects:
        if expand and split_expanded:
            objects_ = objects
            objects = []
            for o in objects_:
                objects.extend(o.split_expanded())

        ## Code for sorting removed because so far unused.

        ## partial workaround for https://github.com/python-caldav/caldav/issues/201
        for obj in objects:
            with contextlib.suppress(Exception):
                obj.load(only_if_unloaded=True)

        return objects

    async def _async_update_data(self) -> CalendarEvent | None:
        """Get the latest data.

        Note: currently this only updates the Calendar Entity to indicate currently active calendar events.
        It would be nice to implement some caching and pre-fetching of events between today and a given horizon, based on sync-tokens.
        """

        start_of_today = dt_util.start_of_local_day()
        start_of_tomorrow = dt_util.start_of_local_day() + timedelta(days=self.days)

        _LOGGER.debug("Updating CalDav data for calendar %s", self.calendar.name)

        # We have to retrieve the results for the whole day as the server
        # won't return events that have already started
        results = await self.hass.async_add_executor_job(
            partial(
                self.calendar.search,
                start=start_of_today,
                end=start_of_tomorrow,
                event=True,
                expand=True,
            ),
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
                _start_of_today: date | datetime
                _start_of_tomorrow: datetime | date
                if self.is_all_day(vevent):
                    start_dt = start_dt.date()
                    _start_of_today = start_of_today.date()
                    _start_of_tomorrow = start_of_tomorrow.date()
                else:
                    _start_of_today = start_of_today
                    _start_of_tomorrow = start_of_tomorrow
                if _start_of_today <= start_dt < _start_of_tomorrow:
                    new_event = event.copy()
                    new_vevent = new_event.instance.vevent  # type: ignore[attr-defined]
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
            self.offset = None
            return None

        # Populate the entity attributes with the event values
        (summary, offset) = extract_offset(
            get_attr_value(vevent, "summary") or "", OFFSET
        )
        self.offset = offset
        return CalendarEvent(
            summary=summary,
            start=self.to_local(vevent.dtstart.value),
            end=self.to_local(self.get_end_date(vevent)),
            location=get_attr_value(vevent, "location"),
            description=get_attr_value(vevent, "description"),
        )

    @staticmethod
    def is_matching(vevent, search):
        """Return if the event matches the filter criteria."""
        if search is None:
            return True

        pattern = re.compile(search)
        return (
            (hasattr(vevent, "summary") and pattern.match(vevent.summary.value))
            or (hasattr(vevent, "location") and pattern.match(vevent.location.value))
            or (
                hasattr(vevent, "description")
                and pattern.match(vevent.description.value)
            )
        )

    @staticmethod
    def is_all_day(vevent):
        """Return if the event last the whole day."""
        return not isinstance(vevent.dtstart.value, datetime)

    @staticmethod
    def is_over(vevent):
        """Return if the event is over."""
        return dt_util.now() >= CalDavUpdateCoordinator.to_datetime(
            CalDavUpdateCoordinator.get_end_date(vevent)
        )

    @staticmethod
    def parse_recurrence_id(recurrence_id: str) -> datetime | date:
        """Convert a recurrence_id string to a datetime or date object."""
        dt = dt_util.parse_datetime(recurrence_id) or dt_util.parse_date(recurrence_id)
        if not dt:
            raise ValueError("Unable to parse recurrence_id %s")
        return dt

    @staticmethod
    def to_datetime(obj: datetime | date) -> datetime:
        """Return a datetime."""
        if isinstance(obj, datetime):
            dt = CalDavUpdateCoordinator.to_local(obj)
            # from a quick peek at the code of to_local we know we'll get a datetime backwhen we provide a datetime. Apparently mypy doesn't know that.
            # this assertion will mypy help understand
            assert isinstance(dt, datetime)
            return dt
        return datetime.combine(obj, time.min).replace(
            tzinfo=dt_util.get_default_time_zone()
        )

    @staticmethod
    def to_local(obj: datetime | date) -> datetime | date:
        """Return a datetime as a local datetime, leaving dates unchanged.

        This handles giving floating times a timezone for comparison
        with all day events and dropping the custom timezone object
        used by the caldav client and dateutil so the datetime can be copied.
        """
        if isinstance(obj, datetime):
            return dt_util.as_local(obj)
        return obj

    @staticmethod
    def get_end_date(obj):
        """Return the end datetime as determined by dtend or duration."""
        if hasattr(obj, "dtend"):
            enddate = obj.dtend.value
        elif hasattr(obj, "duration"):
            enddate = obj.dtstart.value + obj.duration.value
        else:
            enddate = obj.dtstart.value + timedelta(days=1)

        # End date for an all day event is exclusive. This fixes the case where
        # an all day event has a start and end values are the same, or the event
        # has a zero duration.
        if not isinstance(enddate, datetime) and obj.dtstart.value == enddate:
            enddate += timedelta(days=1)

        return enddate
