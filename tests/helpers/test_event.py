"""Test event helpers."""
# pylint: disable=protected-access
import asyncio
import unittest
from datetime import datetime, timedelta

from astral import Astral
import pytest

from homeassistant.setup import setup_component
import homeassistant.core as ha
from homeassistant.const import MATCH_ALL
from homeassistant.helpers.event import (
    track_point_in_utc_time,
    track_point_in_time,
    track_utc_time_change,
    track_time_change,
    track_state_change,
    track_time_interval,
    track_template,
    track_same_state,
    track_sunrise,
    track_sunset,
)
from homeassistant.helpers.template import Template
from homeassistant.components import sun
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant, fire_time_changed
from unittest.mock import patch


class TestEventHelpers(unittest.TestCase):
    """Test the Home Assistant event helpers."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
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

        def specific_run_callback(entity_id, old_state, new_state):
            specific_runs.append(1)

        track_state_change(
            self.hass, 'light.Bowl', specific_run_callback, 'on', 'off')

        @ha.callback
        def wildcard_run_callback(entity_id, old_state, new_state):
            wildcard_runs.append((old_state, new_state))

        track_state_change(self.hass, 'light.Bowl', wildcard_run_callback)

        @asyncio.coroutine
        def wildercard_run_callback(entity_id, old_state, new_state):
            wildercard_runs.append((old_state, new_state))

        track_state_change(self.hass, MATCH_ALL, wildercard_run_callback)

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

    def test_track_template(self):
        """Test tracking template."""
        specific_runs = []
        wildcard_runs = []
        wildercard_runs = []

        template_condition = Template(
            "{{states.switch.test.state == 'on'}}",
            self.hass
        )
        template_condition_var = Template(
            "{{states.switch.test.state == 'on' and test == 5}}",
            self.hass
        )

        self.hass.states.set('switch.test', 'off')

        def specific_run_callback(entity_id, old_state, new_state):
            specific_runs.append(1)

        track_template(self.hass, template_condition, specific_run_callback)

        @ha.callback
        def wildcard_run_callback(entity_id, old_state, new_state):
            wildcard_runs.append((old_state, new_state))

        track_template(self.hass, template_condition, wildcard_run_callback)

        @asyncio.coroutine
        def wildercard_run_callback(entity_id, old_state, new_state):
            wildercard_runs.append((old_state, new_state))

        track_template(
            self.hass, template_condition_var, wildercard_run_callback,
            {'test': 5})

        self.hass.states.set('switch.test', 'on')
        self.hass.block_till_done()

        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))
        self.assertEqual(1, len(wildercard_runs))

        self.hass.states.set('switch.test', 'on')
        self.hass.block_till_done()

        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))
        self.assertEqual(1, len(wildercard_runs))

        self.hass.states.set('switch.test', 'off')
        self.hass.block_till_done()

        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))
        self.assertEqual(1, len(wildercard_runs))

        self.hass.states.set('switch.test', 'off')
        self.hass.block_till_done()

        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))
        self.assertEqual(1, len(wildercard_runs))

        self.hass.states.set('switch.test', 'on')
        self.hass.block_till_done()

        self.assertEqual(2, len(specific_runs))
        self.assertEqual(2, len(wildcard_runs))
        self.assertEqual(2, len(wildercard_runs))

    def test_track_same_state_simple_trigger(self):
        """Test track_same_change with trigger simple."""
        thread_runs = []
        callback_runs = []
        coroutine_runs = []
        period = timedelta(minutes=1)

        def thread_run_callback():
            thread_runs.append(1)

        track_same_state(
            self.hass, period, thread_run_callback,
            lambda _, _2, to_s: to_s.state == 'on',
            entity_ids='light.Bowl')

        @ha.callback
        def callback_run_callback():
            callback_runs.append(1)

        track_same_state(
            self.hass, period, callback_run_callback,
            lambda _, _2, to_s: to_s.state == 'on',
            entity_ids='light.Bowl')

        @asyncio.coroutine
        def coroutine_run_callback():
            coroutine_runs.append(1)

        track_same_state(
            self.hass, period, coroutine_run_callback,
            lambda _, _2, to_s: to_s.state == 'on')

        # Adding state to state machine
        self.hass.states.set("light.Bowl", "on")
        self.hass.block_till_done()
        self.assertEqual(0, len(thread_runs))
        self.assertEqual(0, len(callback_runs))
        self.assertEqual(0, len(coroutine_runs))

        # change time to track and see if they trigger
        future = dt_util.utcnow() + period
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()
        self.assertEqual(1, len(thread_runs))
        self.assertEqual(1, len(callback_runs))
        self.assertEqual(1, len(coroutine_runs))

    def test_track_same_state_simple_no_trigger(self):
        """Test track_same_change with no trigger."""
        callback_runs = []
        period = timedelta(minutes=1)

        @ha.callback
        def callback_run_callback():
            callback_runs.append(1)

        track_same_state(
            self.hass, period, callback_run_callback,
            lambda _, _2, to_s: to_s.state == 'on',
            entity_ids='light.Bowl')

        # Adding state to state machine
        self.hass.states.set("light.Bowl", "on")
        self.hass.block_till_done()
        self.assertEqual(0, len(callback_runs))

        # Change state on state machine
        self.hass.states.set("light.Bowl", "off")
        self.hass.block_till_done()
        self.assertEqual(0, len(callback_runs))

        # change time to track and see if they trigger
        future = dt_util.utcnow() + period
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()
        self.assertEqual(0, len(callback_runs))

    def test_track_same_state_simple_trigger_check_funct(self):
        """Test track_same_change with trigger and check funct."""
        callback_runs = []
        check_func = []
        period = timedelta(minutes=1)

        @ha.callback
        def callback_run_callback():
            callback_runs.append(1)

        @ha.callback
        def async_check_func(entity, from_s, to_s):
            check_func.append((entity, from_s, to_s))
            return True

        track_same_state(
            self.hass, period, callback_run_callback,
            entity_ids='light.Bowl', async_check_same_func=async_check_func)

        # Adding state to state machine
        self.hass.states.set("light.Bowl", "on")
        self.hass.block_till_done()
        self.assertEqual(0, len(callback_runs))
        self.assertEqual('on', check_func[-1][2].state)
        self.assertEqual('light.bowl', check_func[-1][0])

        # change time to track and see if they trigger
        future = dt_util.utcnow() + period
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()
        self.assertEqual(1, len(callback_runs))

    def test_track_time_interval(self):
        """Test tracking time interval."""
        specific_runs = []

        utc_now = dt_util.utcnow()
        unsub = track_time_interval(
            self.hass, lambda x: specific_runs.append(1),
            timedelta(seconds=10)
        )

        self._send_time_changed(utc_now + timedelta(seconds=5))
        self.hass.block_till_done()
        self.assertEqual(0, len(specific_runs))

        self._send_time_changed(utc_now + timedelta(seconds=13))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))

        self._send_time_changed(utc_now + timedelta(minutes=20))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))

        unsub()

        self._send_time_changed(utc_now + timedelta(seconds=30))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))

    def test_track_sunrise(self):
        """Test track the sunrise."""
        latitude = 32.87336
        longitude = 117.22743

        # Setup sun component
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude
        setup_component(self.hass, sun.DOMAIN, {
            sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        # Get next sunrise/sunset
        astral = Astral()
        utc_now = datetime(2014, 5, 24, 12, 0, 0, tzinfo=dt_util.UTC)
        utc_today = utc_now.date()

        mod = -1
        while True:
            next_rising = (astral.sunrise_utc(
                utc_today + timedelta(days=mod), latitude, longitude))
            if next_rising > utc_now:
                break
            mod += 1

        # Track sunrise
        runs = []
        with patch('homeassistant.util.dt.utcnow', return_value=utc_now):
            unsub = track_sunrise(self.hass, lambda: runs.append(1))

        offset_runs = []
        offset = timedelta(minutes=30)
        with patch('homeassistant.util.dt.utcnow', return_value=utc_now):
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
        self.assertEqual(1, len(runs))
        self.assertEqual(1, len(offset_runs))

        unsub()
        unsub2()

        self._send_time_changed(next_rising + offset)
        self.hass.block_till_done()
        self.assertEqual(1, len(runs))
        self.assertEqual(1, len(offset_runs))

    def test_track_sunset(self):
        """Test track the sunset."""
        latitude = 32.87336
        longitude = 117.22743

        # Setup sun component
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude
        setup_component(self.hass, sun.DOMAIN, {
            sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        # Get next sunrise/sunset
        astral = Astral()
        utc_now = datetime(2014, 5, 24, 12, 0, 0, tzinfo=dt_util.UTC)
        utc_today = utc_now.date()

        mod = -1
        while True:
            next_setting = (astral.sunset_utc(
                utc_today + timedelta(days=mod), latitude, longitude))
            if next_setting > utc_now:
                break
            mod += 1

        # Track sunset
        runs = []
        with patch('homeassistant.util.dt.utcnow', return_value=utc_now):
            unsub = track_sunset(self.hass, lambda: runs.append(1))

        offset_runs = []
        offset = timedelta(minutes=30)
        with patch('homeassistant.util.dt.utcnow', return_value=utc_now):
            unsub2 = track_sunset(
                self.hass, lambda: offset_runs.append(1), offset)

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
        self.assertEqual(1, len(runs))
        self.assertEqual(1, len(offset_runs))

        unsub()
        unsub2()

        self._send_time_changed(next_setting + offset)
        self.hass.block_till_done()
        self.assertEqual(1, len(runs))
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

        with pytest.raises(ValueError):
            track_utc_time_change(
                self.hass, lambda x: specific_runs.append(1), year='/two')

        self._send_time_changed(datetime(2014, 5, 2, 0, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(0, len(specific_runs))
