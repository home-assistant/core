"""Class representing a schedule of events."""

from datetime import date, datetime, time, timedelta

from typing import List, Tuple

from .scheduleutil import daily_schedule, events_until, events_after
from .scheduletypes import ScheduleEntry, ScheduleEvent, State


class Schedule:
    """Represents a schedule of events."""

    def __init__(self, entries: List[ScheduleEntry], text: str) -> None:
        """Initialize the schedule."""
        self._day_list = [daily_schedule(
            entries, d) for d in range(0, 7)]
        self.text = text

    def __str__(self):
        """Return a textual description of the Schedule."""
        return self.text

    def has_event(self, today: date) -> bool:
        """Return True if the specified date has any events."""
        return self._day_list[today.weekday()] != []

    def get_latest_event(self, now: datetime, lookback: bool = True) \
            -> Tuple[datetime, State]:
        """
        Return the most recent event before a date/time, or None.

        Keyword arguments:
        lookback -- if True then previous days will be considered when looking
        for a latest event.
        """
        result = self._get_last_event(now.date(), now.tzinfo, now.time())
        if result:
            return result
        if lookback:
            for i in range(1, 7):
                new_now = now - timedelta(days=i)
                result = self._get_last_event(new_now.date(), now.tzinfo)
                if result:
                    return result
        return None

    def get_current_state(self, now: datetime, lookback: bool = True) -> str:
        """
        Return the current state, or None if there is no previous event.

        Keyword arguments:
        lookback -- if True then previous days will be considered when looking
        for a latest event.
        """
        event = self.get_latest_event(now, lookback)
        return event[1] if event else None

    def _get_last_event(self, now: date, tzinfo, until: time = None) \
            -> Tuple[datetime, State]:
        """Find the last event on the given day up until the given time."""
        day = now.weekday()
        if until is not None:
            daily_events = events_until(self._day_list[day], until)
        else:
            daily_events = self._day_list[day]
        if not daily_events:
            return None
        event_time, state = daily_events[-1]   # Just want the last one
        event_time = event_time.replace(tzinfo=tzinfo)
        return datetime.combine(now, event_time), state

    def get_events_today(self, now: date) -> List[ScheduleEvent]:
        """Return all the events on a given day."""
        return self._day_list[now.weekday()]

    def get_next_event_today(self, now: datetime) -> ScheduleEvent:
        """
        Return the next event after the specified datetime.

        This returns the next event on the same day, or None if there are't
        any.
        """
        events = events_after(
            self._day_list[now.weekday()], now.time())
        return events[0] if events else None
