"""Utility methods for schedule parsing."""

from datetime import time
from typing import List

from .scheduletypes import ScheduleEntry, ScheduleEvent


def sort_schedule_events(events: List[ScheduleEvent]) -> List[ScheduleEvent]:
    """Sort events into time order."""
    return sorted(events, key=lambda e: e[0])


def daily_schedule(schedule: List[ScheduleEntry], day: int) \
                   -> List[ScheduleEvent]:
    """Return a single list of events on the given day."""
    events = [event for entry in schedule if day in entry[0]
              for event in entry[1]]
    return sort_schedule_events(events)


def events_after(events: List[ScheduleEvent], after: time) \
                 -> List[ScheduleEvent]:
    """Return events strictly after the given time."""
    return [event for event in events if event[0] > after]


def events_until(events: List[ScheduleEvent],
                 until: time, *, after: time = None) \
                 -> List[ScheduleEvent]:
    """
    Return events up to and including the given time.

    Keyword arguments:
    after -- if specified, only events after this time will be included.
    """
    if after is not None:
        events = events_after(events, after)
    return [event for event in events if event[0] <= until]
