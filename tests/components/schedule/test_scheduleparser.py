"""The tests for the ScheduleParser class."""

from datetime import datetime, time, timedelta
import unittest
import voluptuous as vol

import homeassistant.components.schedule.scheduleparser as sp


class TestScheduleParser(unittest.TestCase):
    """Test the ScheduleParser class."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things needed by all tests."""
        self.parser = sp.ScheduleParser()

    def test_weekday(self):
        """Test parsing of weekday strings."""
        self.assertEqual([5], self.parser.parse_weekdays('Sat'))
        self.assertEqual([0], self.parser.parse_weekdays('Mon'))

    def test_parse_day_range(self):
        """Test parsing of day ranges."""
        self.assertEqual([6, 0, 1], self.parser.parse_weekdays('Sun-Tue'))

    def test_parse_multiple_days(self):
        """Test parsing of mulitple days."""
        self.assertEqual([1, 5, 4, 2, 3], self.parser.parse_weekdays(
            'Tue, Sat, Fri, Wed-Thu'))

    def test_parse_bad_day(self):
        """Test error handling for unrecognised weekdays."""
        with self.assertRaisesRegex(vol.Invalid,
                                    'Bad weekday format: "Blah"'):
            self.parser.parse_weekdays('Blah')

    def test_parse_simple_time(self):
        """Test parsing of time strings."""
        self.assertEqual('01:02:03', self.parser.parse_time(
            '01:02:03').isoformat())
        self.assertEqual(
            '04:05:00', self.parser.parse_time('04:05').isoformat())

    def test_parse_short_time(self):
        """Test time strings don't have to have two-digit hours."""
        self.assertEqual(
            '01:02:03', self.parser.parse_time('1:02:03').isoformat())
        self.assertEqual(
            '04:05:00', self.parser.parse_time('4:05').isoformat())

    def test_parse_bad_time(self):
        """Test error handling for bad time strings."""
        with self.assertRaisesRegex(vol.Invalid, 'Bad time format: "Blah"'):
            self.parser.parse_time('Blah')

    def test_parse_time_delta(self):
        """Test parsing of time delta strings."""
        self.assertEqual(timedelta(hours=2),
                         self.parser.parse_time_delta('2h'))
        self.assertEqual(timedelta(minutes=3),
                         self.parser.parse_time_delta('3m'))
        self.assertEqual(timedelta(seconds=4),
                         self.parser.parse_time_delta('4s'))
        self.assertEqual(timedelta(hours=11, minutes=12, seconds=13),
                         self.parser.parse_time_delta('11h12m13s'))

    def test_parse_time_schedule_part(self):
        """Test parsing of time events or ranges."""
        parser = self.parser
        self.assertEqual([(time(9, 5, 6), 'on')],
                         parser.parse_time_schedule_part('09:05:06'))
        self.assertEqual([(time(9, 5, 6), 'on'), (time(14, 2), 'off')],
                         parser.parse_time_schedule_part('09:05:06-14:02'))
        self.assertEqual([(time(1, 0, 0), 'test')],
                         parser.parse_time_schedule_part('01:00=test'))
        self.assertEqual([(time(9, 5, 6), 'on'), (time(10, 7, 9), 'off')],
                         parser.parse_time_schedule_part('09:05:06+1h2m3s'))

    def test_override_onoff_states(self):
        """Test overriding the default values for on and off states."""
        parser = sp.ScheduleParser(on_state='a', off_state='b')
        self.assertEqual([(time(9, 5, 6), 'a'), (time(14, 2), 'b')],
                         parser.parse_time_schedule_part('09:05:06-14:02'))

    def test_parse_bad_time_part(self):
        """Test error handling for bad time ranges."""
        # Have to put message in a var because of 79-char line length linting
        msg = 'Bad time range format: "01:00-02:00-03:00"'
        with self.assertRaisesRegex(vol.Invalid, msg):
            self.parser.parse_time_schedule_part('01:00-02:00-03:00')
        msg = 'Bad state change format: "a=b=c"'
        with self.assertRaisesRegex(Exception, msg):
            self.parser.parse_time_schedule_part('a=b=c')
        msg = 'Finish time cannot be before start: "10:00-09:59"'
        with self.assertRaisesRegex(Exception, msg):
            self.parser.parse_time_schedule_part('10:00-09:59')
        msg = 'Cannot currently have time range going ' + \
              'past end of day: "23:00\+2h"'
        with self.assertRaisesRegex(Exception, msg):
            self.parser.parse_time_schedule_part('23:00+2h')

    def test_parse_time_schedule(self):
        """Test parsing of a schedule of multiple times."""
        schedule = '01:02, 02:03-04:05, 06:07=wibble'
        self.assertEqual([(time(1, 2), 'on'),
                          (time(2, 3), 'on'),
                          (time(4, 5), 'off'),
                          (time(6, 7), 'wibble')],
                         self.parser.parse_time_schedule(schedule))

    def test_parse_schedule_entry(self):
        """Test parsing of a day list and schedule of multiple times."""
        days = [1, 2, 4]
        schedule = 'Tue-Wed, Fri: 01:02, 02:03-04:05, 06:07=wibble'
        time_schedule = [(time(1, 2), 'on'),
                         (time(2, 3), 'on'),
                         (time(4, 5), 'off'),
                         (time(6, 7), 'wibble')]
        self.assertEqual((days, time_schedule),
                         self.parser.parse_schedule_entry(schedule))

    def test_parse_schedule_line(self):
        """Test parsing of a full schedule."""
        days_1 = [1, 2, 4]
        schedule = 'Tue-Wed, Fri: 01:02, 02:03-04:05,' + \
                   '06:07=wibble; Thu: 14:15:30'
        time_schedule_1 = [(time(1, 2), 'on'), (time(2, 3), 'on'),
                           (time(4, 5), 'off'), (time(6, 7), 'wibble')]
        days_2 = [3]
        time_schedule_2 = [(time(14, 15, 30), 'on')]
        self.assertEqual([(days_1, time_schedule_1),
                          (days_2, time_schedule_2)],
                         self.parser.parse_schedule_line(schedule))

    def test_parse_schedule_line_ignores_whitespace(self):
        """Test whitespace doesn't matter."""
        thin_schedule = 'Tue-Wed,Fri:01:02,02:03-04:05,06:07=wibble,' + \
                        '09:05+2h3m;Thu:14:15:30'
        fat_schedule = ' Tue - Wed , Fri : 01:02 , 02:03 - 04:05 ,' +  \
                       '06:07 = wibble, 09:05 + 2h3m ; Thu : 14:15:30 '
        self.assertEqual(self.parser.parse_schedule_line(thin_schedule),
                         self.parser.parse_schedule_line(fat_schedule))

    def test_parse_stateless_schedule(self):
        """Test parsing a schedule where we're not doing state transitions."""
        parser = sp.ScheduleParser(stateless=True)
        schedule = 'Tue-Wed, Fri: 01:02, 02:03, 04:05'
        days = [1, 2, 4]
        times = [(time(1, 2), 'on'), (time(2, 3), 'on'), (time(4, 5), 'on')]
        self.assertEqual([(days, times)], parser.parse_schedule_line(schedule))

    def test_parse_bad_stateless_schedule(self):
        """Test parsing errors for stateless schedules."""
        parser = sp.ScheduleParser(stateless=True)

        # Can't do time ranges
        with self.assertRaisesRegex(vol.Invalid,
                                    'Bad time format: "01:02-03:04"'):
            parser.parse_schedule_line('Tue-Wed, Fri: 01:02-03:04')

        # Nor in time delta form
        with self.assertRaisesRegex(vol.Invalid,
                                    'Bad time format: "01:02\+3h"'):
            parser.parse_schedule_line('Tue-Wed, Fri: 01:02+3h')

        # Also can't do specific states
        with self.assertRaisesRegex(vol.Invalid,
                                    'Bad time format: "01:02=a"'):
            parser.parse_schedule_line('Tue-Wed, Fri: 01:02=a')

    def test_parse_schedule(self):
        """Test parsing into a Schedule object."""
        test_date = datetime(2018, 4, 6, 7, 7)
        schedule_text = 'Tue-Wed, Fri: 01:02, 02:03-04:05,' + \
                        '06:07=wibble; Thu: 14:15:30'
        schedule = self.parser.parse_schedule(schedule_text)
        self.assertEqual('wibble', schedule.get_current_state(test_date))
