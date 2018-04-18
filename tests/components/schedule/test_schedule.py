"""The tests for the Schedule class."""

from datetime import date, datetime, time
import unittest

from homeassistant.components.schedule.schedule import Schedule
from homeassistant.components.schedule.scheduleparser import ScheduleParser

parser = ScheduleParser()
friday = date(1999, 12, 31)
saturday = date(2000, 1, 1)
monday = date(2000, 1, 3)
SCHEDULE = 'Mon-Fri: 09:00=a, 10:00=b, 11:00=c'


def dt(day: date, time: str) -> datetime:
    """Convenience function to make tests easier to read."""
    t = parser.parse_time(time)
    return datetime.combine(day, t)


class TestSchedule(unittest.TestCase):
    """Tests for the Schedule class."""

    def test_has_event(self):
        """Test has_event works."""
        schedule = parser.parse_schedule(SCHEDULE)
        self.assertTrue(schedule.has_event(monday))
        self.assertFalse(schedule.has_event(saturday))

    def test_preserves_text(self):
        """Test has_event works."""
        schedule = Schedule(parser.parse_schedule_line(SCHEDULE), SCHEDULE)
        self.assertEqual(SCHEDULE, str(schedule))

    def test_get_latest_event(self):
        """Test get_latest_event works."""
        schedule = parser.parse_schedule(SCHEDULE)
        self.assertEqual((dt(monday, '09:00'), "a"),
                         schedule.get_latest_event(dt(monday, '09:30')))
        self.assertEqual((dt(monday, '10:00'), "b"),
                         schedule.get_latest_event(dt(monday, '10:00')))
        self.assertEqual((dt(monday, '11:00'), "c"),
                         schedule.get_latest_event(dt(monday, '23:00')))

    def test_looking_back_to_prior_state(self):
        """Test that when lookback is true that it scans the previous days."""
        schedule = parser.parse_schedule(SCHEDULE)
        self.assertIsNone(schedule.get_latest_event(
            dt(saturday, '09:30'), lookback=False))
        self.assertEqual((dt(friday, '11:00'), "c"),
                         schedule.get_latest_event(dt(saturday, '09:30')))

    def test_get_events_today(self):
        """Test get_event_today works."""
        schedule = parser.parse_schedule(SCHEDULE)
        events = schedule.get_events_today(monday)
        self.assertEqual(3, len(events))
        self.assertEqual((time(9, 0), 'a'), events[0])
        self.assertEqual((time(10, 0), 'b'), events[1])
        self.assertEqual((time(11, 0), 'c'), events[2])

        self.assertEqual([], schedule.get_events_today(saturday))

    def test_get_current_state(self):
        """Test getting the current state of the schedule."""
        schedule = parser.parse_schedule(SCHEDULE)
        self.assertEqual("a", schedule.get_current_state(dt(monday, '09:30')))
        self.assertEqual("c", schedule.get_current_state(dt(monday, '08:30')))
        self.assertIsNone(schedule.get_current_state(dt(saturday, '09:30'),
                                                     lookback=False))

    def test_get_next_event_today(self):
        """Test get_next_event_today works."""
        schedule = parser.parse_schedule(SCHEDULE)
        self.assertEqual((time(9, 0), "a"),
                         schedule.get_next_event_today(dt(monday, '00:00')))
        self.assertEqual((time(10, 0), "b"),
                         schedule.get_next_event_today(dt(monday, '09:00')))
        self.assertIsNone(schedule.get_next_event_today(dt(monday, '11:00')))

    def test_midnight(self):
        """Test events set to midnight behave correctly."""
        schedule_text = 'Mon-Fri: 00:00=a'
        schedule = parser.parse_schedule(schedule_text)
        self.assertEqual((dt(monday, '00:00'), "a"),
                         schedule.get_latest_event(dt(monday, '00:00')))
        self.assertIsNone(schedule.get_next_event_today(dt(monday, '00:00')))
