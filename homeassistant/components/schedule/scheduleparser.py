"""Class to parse a textual schedule into a usuable structure."""

from datetime import date, datetime, time, timedelta
import re
import voluptuous as vol

from typing import Any, List

from homeassistant.const import STATE_ON, STATE_OFF
import homeassistant.helpers.config_validation as cv

from .schedule import Schedule
from .scheduletypes import ScheduleEntry, ScheduleEvent


def is_valid_schedule(value: Any) -> Schedule:
    """Validate that the entry is a valid schedule."""
    config_list = [cv.string(item) for item in cv.ensure_list(value)]
    schedule_text = '; '.join(config_list)
    parser = ScheduleParser()
    return parser.parse_schedule(schedule_text)


class ScheduleParser:
    """
    Class providing facilities to parse schedule text.

    The class may be run in one of two modes:
    - Stateful (the default) allows schedules to specify on-off ranges or even
      specifically named states (e.g. 'cold', 'warm', 'hot')
    - Stateless means that the schedule consists purely of events and doesn't
      allow state transitions.
    In stateless mode, the schedule returned consists entirely of 'on' events.
    """

    _day_map = {'Mon': 0, 'Tue': 1, 'Wed': 2,
                'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
    _weekday_pattern = re.compile(r'^(?P<start>\w+)\s*\-\s*(?P<finish>\w+)$')
    _time_pattern = re.compile(r'^\d?\d:\d\d$')
    _time_seconds_pattern = re.compile(r'^\d?\d:\d\d:\d\d$')
    _time_delta_pattern = re.compile(
        r'^((?P<hours>\d+)h)?((?P<mins>\d+)m)?((?P<secs>\d+)s)?$')

    def __init__(self, *, on_state: str = STATE_ON,
                 off_state: str = STATE_OFF, stateless: bool = False) \
            -> None:
        """
        Initialise the parser.

        Keyword arguments:
        on_state -- the string to use to represent on (default 'on')
        off_state -- the string to use to represent off (default 'off')
        stateless -- if False then do not allow event states
        """
        self.on_state = on_state
        self.off_state = off_state
        self.stateless = stateless

    def parse_weekdays(self, text: str) -> List[int]:
        """
        Parse a string of the form 'Mon-Wed,Fri' into a list of integers.

        Note that the integers correspond to the Python day numbers of those
        days, not ISO standard day numbers.
        """
        parts = [p.strip() for p in text.split(',')]
        result = []   # type: List[int]
        for part in parts:
            match = self._weekday_pattern.match(part)
            if match:
                # Range
                start, finish = self.weekday(match.group(
                    'start')), self.weekday(match.group('finish'))
                result += [start]
                while start != finish:
                    start = (start + 1) % 7
                    result += [start]
            else:
                # Singleton
                result += [self.weekday(part)]
        return result

    def weekday(self, text: str) -> int:
        """Convert a single day string into a Python day number."""
        result = self._day_map.get(text)
        if result is None:
            raise vol.Invalid('Bad weekday format: "{}"'.format(text))
        return result

    def parse_time(self, text: str) -> time:
        """Parse a string of the form H:M or H:M:S into a time object."""
        text = text.strip()
        if self._time_pattern.match(text):
            return datetime.strptime(text, '%H:%M').time()
        elif self._time_seconds_pattern.match(text):
            return datetime.strptime(text, '%H:%M:%S').time()
        else:
            raise vol.Invalid('Bad time format: "{}"'.format(text))

    def parse_time_delta(self, text: str) -> timedelta:
        """
        Parse a string of the form XhYmZx into a timedelta object.

        All of the components of the string are optional, so you can do
        things like '2h1s' or '1m'.
        """
        text = text.strip()
        match = self._time_delta_pattern.match(text)
        if match:
            hours = int(match.group('hours') or 0)
            mins = int(match.group('mins') or 0)
            secs = int(match.group('secs') or 0)
            return timedelta(hours=hours, minutes=mins, seconds=secs)
        else:
            raise vol.Invalid('Bad time delta format: "{}"'.format(text))

    def parse_time_schedule_part(self, text: str) -> List[ScheduleEvent]:
        """
        Parse a time range string into a list of events.

        The string may be one of:
        - Simple time: 11:15[:30] (in stateless mode only this is supported)
        - On/off time range: 11:15-12:30
        - On/off time range: 11:15+1h15m
        - Time and state: 11:15=idle
        """
        if self.stateless:
            return [(self.parse_time(text), self.on_state)]

        if '-' in text:
            bits = text.split('-')
            if len(bits) != 2:
                msg = 'Bad time range format: "{}"'.format(text)
                raise vol.Invalid(msg)
            start, finish = bits
            start_time = self.parse_time(start)
            finish_time = self.parse_time(finish)
            if finish_time < start_time:
                msg = 'Finish time cannot be before start: "{}"'.format(text)
                raise vol.Invalid(msg)
            return [(start_time, self.on_state),
                    (finish_time, self.off_state)]
        elif '+' in text:
            bits = text.split('+')
            if len(bits) != 2:
                msg = 'Bad time range format: "{}"'.format(text)
                raise vol.Invalid(msg)
            start, delta = bits
            start_time = self.parse_time(start)
            time_delta = self.parse_time_delta(delta)
            # We can only apply a time delta to a datetime, not a time
            base_date = date(2000, 1, 1)
            start_datetime = datetime.combine(base_date, start_time)
            end_datetime = start_datetime + time_delta
            if end_datetime.date() != base_date:
                msg = ('Cannot currently have time range going past end ' +
                       'of day: "{}"').format(text)
                raise vol.Invalid(msg)
            return [(start_time, self.on_state),
                    (end_datetime.time(), self.off_state)]
        elif '=' in text:
            bits = text.split('=')
            if len(bits) != 2:
                msg = 'Bad state change format: "{}"'.format(text)
                raise vol.Invalid(msg)
            time_str, state = bits
            return [(self.parse_time(time_str), state.strip())]
        else:
            return [(self.parse_time(text), self.on_state)]

    def parse_time_schedule(self, text: str) -> List[ScheduleEvent]:
        """
        Parse a string into a list of time events.

        Example: '10:00-11:15, 12:30-14:45'
        """
        result = []   # type: List[ScheduleEvent]
        for part in text.split(','):
            result += self.parse_time_schedule_part(part)
        return result

    def parse_schedule_entry(self, text: str) -> ScheduleEntry:
        """
        Parse a string into a ScheduleEntry structure.

        Example: 'Mon-Fri: 10:00-11:15, 12:30-14:45'
        """
        bits = text.split(':')
        if len(bits) < 2:
            raise vol.Invalid('Bad schedule format: "{}"'.format(text))
        days = bits[0]
        times = ':'.join(bits[1:])
        return (self.parse_weekdays(days), self.parse_time_schedule(times))

    def parse_schedule_line(self, text: str) -> List[ScheduleEntry]:
        """
        Parse a string separated with ';' into a list of ScheduleEntries.

        Example: 'Mon-Fri: 10:00-11:15; Sat: 09:00-12:15'
        """
        return [self.parse_schedule_entry(p) for p in text.split(';')]

    def parse_schedule(self, text: str) -> Schedule:
        """
        Parse a string separated with ';' into a Schedule object.

        Example: 'Mon-Fri: 10:00-11:15; Sat: 09:00-12:15'
        """
        return Schedule(self.parse_schedule_line(text), text)
