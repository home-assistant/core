"""Data update coordinator for caldav."""

from datetime import date, datetime, time, timedelta
import logging
import re
from typing import TYPE_CHECKING, Any, override

import caldav
from dateutil import rrule as dateutil_rrule
import icalendar

from homeassistant.components.calendar import CalendarEvent, extract_offset
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import get_attr_value

if TYPE_CHECKING:
    from . import CalDavConfigEntry

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)
OFFSET = "!!"


def _as_list(value: Any) -> list[Any]:
    """Wrap a single icalendar property value in a list, or return it as-is."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _get_vevent(event: caldav.CalendarObjectResource) -> icalendar.cal.Component | None:
    """Return the VEVENT component of a caldav object, or None if it has none."""
    return next(iter(event.icalendar_instance.walk("VEVENT")), None)


def _rruleset(vevent: icalendar.cal.Component) -> dateutil_rrule.rruleset | None:
    """Build the recurrence set for a VEVENT, or None if it does not recur."""
    if "RRULE" not in vevent and "RDATE" not in vevent:
        return None
    dtstart = vevent["DTSTART"].dt
    ruleset = dateutil_rrule.rruleset()
    for rrule in _as_list(vevent.get("RRULE")):
        rule_str = rrule.to_ical().decode()
        if isinstance(dtstart, datetime) and dtstart.tzinfo is not None:
            # dateutil requires UNTIL in UTC when DTSTART is timezone-aware; some
            # servers send a naive UNTIL, which vobject tolerated.
            rule_str = ";".join(
                f"{part}Z"
                if part.upper().startswith("UNTIL=") and not part.endswith("Z")
                else part
                for part in rule_str.split(";")
            )
        rule = dateutil_rrule.rrulestr(rule_str, dtstart=dtstart)
        assert isinstance(rule, dateutil_rrule.rrule)
        ruleset.rrule(rule)
    for rdate in _as_list(vevent.get("RDATE")):
        for value in _as_list(rdate.dts):
            ruleset.rdate(value.dt)
    for exdate in _as_list(vevent.get("EXDATE")):
        for value in _as_list(exdate.dts):
            ruleset.exdate(value.dt)
    return ruleset


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
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )
        self.calendar = calendar
        self.days = days
        self.include_all_day = include_all_day
        self.search = search
        self.offset: timedelta | None = None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        return await hass.async_add_executor_job(self._get_events, start_date, end_date)

    def _get_events(
        self, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Fetch and parse events in a specific time frame."""
        vevent_list = self.calendar.search(
            start=start_date,
            end=end_date,
            event=True,
            expand=True,
        )
        event_list = []
        for event in vevent_list:
            if (vevent := _get_vevent(event)) is None:
                _LOGGER.warning("Skipped event with missing 'vevent' property")
                continue
            if not self.is_matching(vevent, self.search):
                continue
            event_list.append(
                CalendarEvent(
                    summary=get_attr_value(vevent, "summary") or "",
                    start=self.to_local(vevent["DTSTART"].dt),
                    end=self.to_local(self.get_end_date(vevent)),
                    location=get_attr_value(vevent, "location"),
                    description=get_attr_value(vevent, "description"),
                    uid=get_attr_value(vevent, "uid"),
                    recurrence_id=get_attr_value(vevent, "recurrence_id"),
                )
            )

        return event_list

    @override
    async def _async_update_data(self) -> CalendarEvent | None:
        """Get the latest data."""
        start_of_today = dt_util.start_of_local_day()
        start_of_tomorrow = dt_util.start_of_local_day() + timedelta(days=self.days)

        event, offset = await self.hass.async_add_executor_job(
            self._get_next_event, start_of_today, start_of_tomorrow
        )
        self.offset = offset
        return event

    def _get_next_event(
        self, start_of_today: datetime, start_of_tomorrow: datetime
    ) -> tuple[CalendarEvent | None, timedelta | None]:
        """Fetch and parse the next matching event."""
        # We have to retrieve the results for the whole day as the server
        # won't return events that have already started
        results = self.calendar.search(
            start=start_of_today,
            end=start_of_tomorrow,
            event=True,
            expand=True,
        )

        # Create new events for each recurrence of an event that happens today.
        # For recurring events, some servers return the original
        # event with recurrence rules
        # and they would not be properly parsed using their original start/end dates.
        new_events = []
        for event in results:
            if (vevent := _get_vevent(event)) is None:
                _LOGGER.warning("Skipped event with missing 'vevent' property")
                continue
            start_dt: date | datetime
            for start_dt in _rruleset(vevent) or []:
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
                    # The copy has a VEVENT because the source did (checked above)
                    new_vevent = _get_vevent(new_event)
                    assert new_vevent is not None
                    if "DTEND" in new_vevent:
                        dur = new_vevent["DTEND"].dt - new_vevent["DTSTART"].dt
                        new_vevent["DTEND"] = icalendar.prop.vDDDTypes(start_dt + dur)
                    new_vevent["DTSTART"] = icalendar.prop.vDDDTypes(start_dt)
                    new_events.append(new_event)
                elif _start_of_tomorrow <= start_dt:
                    break
        vevents = [
            vevent
            for event in results + new_events
            if (vevent := _get_vevent(event)) is not None
        ]

        # dtstart can be a date or datetime depending if the event lasts a
        # whole day. Convert everything to datetime to be able to sort it
        vevents.sort(key=lambda x: self.to_datetime(x["DTSTART"].dt))

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
            return None, None

        # Populate the entity attributes with the event values
        (summary, offset) = extract_offset(
            get_attr_value(vevent, "summary") or "", OFFSET
        )
        next_event = CalendarEvent(
            summary=summary,
            start=self.to_local(vevent["DTSTART"].dt),
            end=self.to_local(self.get_end_date(vevent)),
            location=get_attr_value(vevent, "location"),
            description=get_attr_value(vevent, "description"),
            uid=get_attr_value(vevent, "uid"),
            recurrence_id=get_attr_value(vevent, "recurrence_id"),
        )
        return next_event, offset

    @staticmethod
    def is_matching(vevent, search):
        """Return if the event matches the filter criteria."""
        if search is None:
            return True

        pattern = re.compile(search)
        return any(
            (value := vevent.get(field)) is not None and pattern.match(str(value))
            for field in ("SUMMARY", "LOCATION", "DESCRIPTION")
        )

    @staticmethod
    def is_all_day(vevent):
        """Return if the event lasts the whole day."""
        return not isinstance(vevent["DTSTART"].dt, datetime)

    @staticmethod
    def is_over(vevent):
        """Return if the event is over."""
        return dt_util.now() >= CalDavUpdateCoordinator.to_datetime(
            CalDavUpdateCoordinator.get_end_date(vevent)
        )

    @staticmethod
    def to_datetime(obj):
        """Return a datetime."""
        if isinstance(obj, datetime):
            return CalDavUpdateCoordinator.to_local(obj)
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
        if "DTEND" in obj:
            enddate = obj["DTEND"].dt
        elif "DURATION" in obj:
            enddate = obj["DTSTART"].dt + obj["DURATION"].dt
        else:
            enddate = obj["DTSTART"].dt + timedelta(days=1)

        # End date for an all day event is exclusive. This fixes the case where
        # an all day event has a start and end values are the same, or the event
        # has a zero duration.
        if not isinstance(enddate, datetime) and obj["DTSTART"].dt == enddate:
            enddate += timedelta(days=1)

        return enddate
