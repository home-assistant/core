"""Test event helpers."""
# pylint: disable=protected-access,too-many-public-methods
# pylint: disable=too-few-public-methods
import unittest
from datetime import datetime, timedelta

from astral import Astral

import homeassistant.core as ha
from homeassistant.const import MATCH_ALL
from homeassistant.helpers.event import (
    track_point_in_utc_time,
    track_point_in_time,
    track_utc_time_change,
    track_time_change,
    track_state_change,
    track_sunrise,
    track_sunset,
)
from homeassistant.components import sun
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant


class TestEventHelpers(unittest.TestCase):
    """Test the Home Assistant event helpers."""

    def setUp(self):     # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_track_point_in_time(self):
        """Test track point in time."""
        before_birthday = datetime(1985, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC)
        birthday_paulus = datetime(1986, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC)
        after_birthday = datetime(1987, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC)

        runs = []

        track_point_in_utc_time(
            self.hass, lambda x: runs.append(1), birthday_paulus)

        self._send_time_changed(before_birthday)
        self.hass.block_till_done()
        self.assertEqual(0, len(runs))

        self._send_time_changed(birthday_paulus)
        self.hass.block_till_done()
        self.assertEqual(1, len(runs))

        # A point in time tracker will only fire once, this should do nothing
        self._send_time_changed(birthday_paulus)
        self.hass.block_till_done()
        self.assertEqual(1, len(runs))

        track_point_in_time(
            self.hass, lambda x: runs.append(1), birthday_paulus)

        self._send_time_changed(after_birthday)
        self.hass.block_till_done()
        self.assertEqual(2, len(runs))

        unsub = track_point_in_time(
            self.hass, lambda x: runs.append(1), birthday_paulus)
        unsub()

        self._send_time_changed(after_birthday)
        self.hass.block_till_done()
        self.assertEqual(2, len(runs))

    def test_track_time_change(self):
        """Test tracking time change."""
        wildcard_runs = []
        specific_runs = []

        unsub = track_time_change(self.hass, lambda x: wildcard_runs.append(1))
        unsub_utc = track_utc_time_change(
            self.hass, lambda x: specific_runs.append(1), second=[0, 30])

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 15))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(2, len(wildcard_runs))

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 30))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))
        self.assertEqual(3, len(wildcard_runs))

        unsub()
        unsub_utc()

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 30))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))
        self.assertEqual(3, len(wildcard_runs))

    def test_track_state_change(self):
        """Test track_state_change."""
        # 2 lists to track how often our callbacks get called
        specific_runs = []
        wildcard_runs = []
        wildercard_runs = []

        track_state_change(
            self.hass, 'light.Bowl', lambda a, b, c: specific_runs.append(1),
            'on', 'off')

        track_state_change(
            self.hass, 'light.Bowl',
            lambda _, old_s, new_s: wildcard_runs.append((old_s, new_s)))

        track_state_change(
            self.hass, MATCH_ALL,
            lambda _, old_s, new_s: wildercard_runs.append((old_s, new_s)))

        # Adding state to state machine
        self.hass.states.set("light.Bowl", "on")
        self.hass.block_till_done()
        self.assertEqual(0, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))
        self.assertEqual(1, len(wildercard_runs))
        self.assertIsNone(wildcard_runs[-1][0])
        self.assertIsNotNone(wildcard_runs[-1][1])

        # Set same state should not trigger a state change/listener
        self.hass.states.set('light.Bowl', 'on')
        self.hass.block_till_done()
        self.assertEqual(0, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))
        self.assertEqual(1, len(wildercard_runs))

        # State change off -> on
        self.hass.states.set('light.Bowl', 'off')
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(2, len(wildcard_runs))
        self.assertEqual(2, len(wildercard_runs))

        # State change off -> off
        self.hass.states.set('light.Bowl', 'off', {"some_attr": 1})
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(3, len(wildcard_runs))
        self.assertEqual(3, len(wildercard_runs))

        # State change off -> on
        self.hass.states.set('light.Bowl', 'on')
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(4, len(wildcard_runs))
        self.assertEqual(4, len(wildercard_runs))

        self.hass.states.remove('light.bowl')
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(5, len(wildcard_runs))
        self.assertEqual(5, len(wildercard_runs))
        self.assertIsNotNone(wildcard_runs[-1][0])
        self.assertIsNone(wildcard_runs[-1][1])
        self.assertIsNotNone(wildercard_runs[-1][0])
        self.assertIsNone(wildercard_runs[-1][1])

        # Set state for different entity id
        self.hass.states.set('switch.kitchen', 'on')
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(5, len(wildcard_runs))
        self.assertEqual(6, len(wildercard_runs))

    def test_track_sunrise(self):
        """Test track the sunrise."""
        latitude = 32.87336
        longitude = 117.22743

        # Setup sun component
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude
        sun.setup(self.hass, {sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        # Get next sunrise/sunset
        astral = Astral()
        utc_now = dt_util.utcnow()

        mod = -1
        while True:
            next_rising = (astral.sunrise_utc(utc_now +
                           timedelta(days=mod), latitude, longitude))
            if next_rising > utc_now:
                break
            mod += 1

        # Track sunrise
        runs = []
        unsub = track_sunrise(self.hass, lambda: runs.append(1))

        offset_runs = []
        offset = timedelta(minutes=30)
        unsub2 = track_sunrise(self.hass, lambda: offset_runs.append(1),
                               offset)

        # run tests
        self._send_time_changed(next_rising - offset)
        self.hass.block_till_done()
        self.assertEqual(0, len(runs))
        self.assertEqual(0, len(offset_runs))

        self._send_time_changed(next_rising)
        self.hass.block_till_done()
        self.assertEqual(1, len(runs))
        self.assertEqual(0, len(offset_runs))

        self._send_time_changed(next_rising + offset)
        self.hass.block_till_done()
        self.assertEqual(2, len(runs))
        self.assertEqual(1, len(offset_runs))

        unsub()
        unsub2()

        self._send_time_changed(next_rising + offset)
        self.hass.block_till_done()
        self.assertEqual(2, len(runs))
        self.assertEqual(1, len(offset_runs))

    def test_track_sunset(self):
        """Test track the sunset."""
        latitude = 32.87336
        longitude = 117.22743

        # Setup sun component
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude
        sun.setup(self.hass, {sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        # Get next sunrise/sunset
        astral = Astral()
        utc_now = dt_util.utcnow()

        mod = -1
        while True:
            next_setting = (astral.sunset_utc(utc_now +
                            timedelta(days=mod), latitude, longitude))
            if next_setting > utc_now:
                break
            mod += 1

        # Track sunset
        runs = []
        unsub = track_sunset(self.hass, lambda: runs.append(1))

        offset_runs = []
        offset = timedelta(minutes=30)
        unsub2 = track_sunset(self.hass, lambda: offset_runs.append(1), offset)

        # Run tests
        self._send_time_changed(next_setting - offset)
        self.hass.block_till_done()
        self.assertEqual(0, len(runs))
        self.assertEqual(0, len(offset_runs))

        self._send_time_changed(next_setting)
        self.hass.block_till_done()
        self.assertEqual(1, len(runs))
        self.assertEqual(0, len(offset_runs))

        self._send_time_changed(next_setting + offset)
        self.hass.block_till_done()
        self.assertEqual(2, len(runs))
        self.assertEqual(1, len(offset_runs))

        unsub()
        unsub2()

        self._send_time_changed(next_setting + offset)
        self.hass.block_till_done()
        self.assertEqual(2, len(runs))
        self.assertEqual(1, len(offset_runs))

    def _send_time_changed(self, now):
        """Send a time changed event."""
        self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: now})

    def test_periodic_task_minute(self):
        """Test periodic tasks per minute."""
        specific_runs = []

        unsub = track_utc_time_change(
            self.hass, lambda x: specific_runs.append(1), minute='/5')

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))

        self._send_time_changed(datetime(2014, 5, 24, 12, 3, 0))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))

        self._send_time_changed(datetime(2014, 5, 24, 12, 5, 0))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))

        unsub()

        self._send_time_changed(datetime(2014, 5, 24, 12, 5, 0))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))

    def test_periodic_task_hour(self):
        """Test periodic tasks per hour."""
        specific_runs = []

        unsub = track_utc_time_change(
            self.hass, lambda x: specific_runs.append(1), hour='/2')

        self._send_time_changed(datetime(2014, 5, 24, 22, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))

        self._send_time_changed(datetime(2014, 5, 24, 23, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))

        self._send_time_changed(datetime(2014, 5, 24, 0, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))

        self._send_time_changed(datetime(2014, 5, 25, 1, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))

        self._send_time_changed(datetime(2014, 5, 25, 2, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(3, len(specific_runs))

        unsub()

        self._send_time_changed(datetime(2014, 5, 25, 2, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(3, len(specific_runs))

    def test_periodic_task_day(self):
        """Test periodic tasks per day."""
        specific_runs = []

        unsub = track_utc_time_change(
            self.hass, lambda x: specific_runs.append(1), day='/2')

        self._send_time_changed(datetime(2014, 5, 2, 0, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))

        self._send_time_changed(datetime(2014, 5, 3, 12, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))

        self._send_time_changed(datetime(2014, 5, 4, 0, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))

        unsub()

        self._send_time_changed(datetime(2014, 5, 4, 0, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))

    def test_periodic_task_year(self):
        """Test periodic tasks per year."""
        specific_runs = []

        unsub = track_utc_time_change(
            self.hass, lambda x: specific_runs.append(1), year='/2')

        self._send_time_changed(datetime(2014, 5, 2, 0, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))

        self._send_time_changed(datetime(2015, 5, 2, 0, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))

        self._send_time_changed(datetime(2016, 5, 2, 0, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))

        unsub()

        self._send_time_changed(datetime(2016, 5, 2, 0, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))

    def test_periodic_task_wrong_input(self):
        """Test periodic tasks with wrong input."""
        specific_runs = []

        track_utc_time_change(
            self.hass, lambda x: specific_runs.append(1), year='/two')

        self._send_time_changed(datetime(2014, 5, 2, 0, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(0, len(specific_runs))
