"""The tests for the scheduleutil module."""

from datetime import time

from homeassistant.components.schedule.scheduleparser import ScheduleParser
from homeassistant.components.schedule.scheduleutil \
    import sort_schedule_events, daily_schedule, events_until

parser = ScheduleParser()


def test_sort_schedule_events():
    """Test schedule event sorting."""
    schedule = parser.parse_time_schedule('10:00=b, 9:00=a, 11:00=c')
    events = sort_schedule_events(schedule)
    assert time(9, 0) == events[0][0]
    assert time(10, 0) == events[1][0]
    assert time(11, 0) == events[2][0]


def test_build_daily_schedule():
    """Test filtering for events on a specific day."""
    schedule = parser.parse_schedule_line(
        'Tue-Wed: 14:00=a, 16:00=c; Wed-Thu: 15:00=b, 16:00=d')
    assert [(time(14, 0), 'a'), (time(16, 0), 'c')
            ] == daily_schedule(schedule, 1)  # Tue
    assert [(time(14, 0), 'a'),
            (time(15, 0), 'b'),
            (time(16, 0), 'c'),
            (time(16, 0), 'd')] == daily_schedule(schedule, 2)  # Wed
    assert [(time(15, 0), 'b'), (time(16, 0), 'd')
            ] == daily_schedule(schedule, 3)  # Thu
    assert [] == daily_schedule(schedule, 5)  # Fri


def test_events_until():
    """Test finding events up to a specific time."""
    events = parser.parse_time_schedule('09:00=a, 10:00=b, 11:00=c')
    assert [] == events_until(events, time(8, 0))
    assert [] == events_until(events, time(9, 30), after=time(9, 0))
    assert [] == events_until(events, time(23, 0), after=time(11, 0))
    assert [(time(9, 0), 'a')] == events_until(
        events, time(9, 30), after=time(8, 0))
    assert [(time(10, 0), 'b')] == events_until(
        events, time(10, 0), after=time(9, 0))
