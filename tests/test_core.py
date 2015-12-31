"""
tests.test_core
~~~~~~~~~~~~~~~~~

Provides tests to verify that Home Assistant core works.
"""
# pylint: disable=protected-access,too-many-public-methods
# pylint: disable=too-few-public-methods
import os
import unittest
from unittest.mock import patch
import time
import threading
from datetime import datetime, timedelta

import pytz

import homeassistant.core as ha
from homeassistant.exceptions import (
    HomeAssistantError, InvalidEntityFormatError)
import homeassistant.util.dt as dt_util
from homeassistant.helpers.event import track_state_change
from homeassistant.const import (
    __version__, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    ATTR_FRIENDLY_NAME, TEMP_CELCIUS,
    TEMP_FAHRENHEIT)

PST = pytz.timezone('America/Los_Angeles')


class TestHomeAssistant(unittest.TestCase):
    """
    Tests the Home Assistant core classes.
    """

    def setUp(self):     # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        self.hass = ha.HomeAssistant()
        self.hass.states.set("light.Bowl", "on")
        self.hass.states.set("switch.AC", "off")

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        try:
            self.hass.stop()
        except HomeAssistantError:
            # Already stopped after the block till stopped test
            pass

    def test_start(self):
        calls = []
        self.hass.bus.listen_once(EVENT_HOMEASSISTANT_START,
                                  lambda event: calls.append(1))
        self.hass.start()
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(calls))

    # @patch('homeassistant.core.time.sleep')
    def test_block_till_stoped(self):
        """ Test if we can block till stop service is called. """
        with patch('time.sleep'):
            blocking_thread = threading.Thread(
                target=self.hass.block_till_stopped)

            self.assertFalse(blocking_thread.is_alive())

            blocking_thread.start()

            self.assertTrue(blocking_thread.is_alive())

            self.hass.services.call(ha.DOMAIN, ha.SERVICE_HOMEASSISTANT_STOP)
            self.hass.pool.block_till_done()

        # Wait for thread to stop
        for _ in range(20):
            if not blocking_thread.is_alive():
                break
            time.sleep(0.05)

        self.assertFalse(blocking_thread.is_alive())

    def test_stopping_with_keyboardinterrupt(self):
        calls = []
        self.hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                                  lambda event: calls.append(1))

        def raise_keyboardinterrupt(length):
            raise KeyboardInterrupt

        with patch('homeassistant.core.time.sleep', raise_keyboardinterrupt):
            self.hass.block_till_stopped()

        self.assertEqual(1, len(calls))

    def test_track_point_in_time(self):
        """ Test track point in time. """
        before_birthday = datetime(1985, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC)
        birthday_paulus = datetime(1986, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC)
        after_birthday = datetime(1987, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC)

        runs = []

        self.hass.track_point_in_utc_time(
            lambda x: runs.append(1), birthday_paulus)

        self._send_time_changed(before_birthday)
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(runs))

        self._send_time_changed(birthday_paulus)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(runs))

        # A point in time tracker will only fire once, this should do nothing
        self._send_time_changed(birthday_paulus)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(runs))

        self.hass.track_point_in_time(
            lambda x: runs.append(1), birthday_paulus)

        self._send_time_changed(after_birthday)
        self.hass.pool.block_till_done()
        self.assertEqual(2, len(runs))

    def test_track_time_change(self):
        """ Test tracking time change. """
        wildcard_runs = []
        specific_runs = []

        self.hass.track_time_change(lambda x: wildcard_runs.append(1))
        self.hass.track_utc_time_change(
            lambda x: specific_runs.append(1), second=[0, 30])

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 0))
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 15))
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(2, len(wildcard_runs))

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 30))
        self.hass.pool.block_till_done()
        self.assertEqual(2, len(specific_runs))
        self.assertEqual(3, len(wildcard_runs))

    def _send_time_changed(self, now):
        """ Send a time changed event. """
        self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: now})


class TestEvent(unittest.TestCase):
    """ Test Event class. """
    def test_eq(self):
        now = dt_util.utcnow()
        data = {'some': 'attr'}
        event1, event2 = [
            ha.Event('some_type', data, time_fired=now)
            for _ in range(2)
        ]

        self.assertEqual(event1, event2)

    def test_repr(self):
        """ Test that repr method works. #MoreCoverage """
        self.assertEqual(
            "<Event TestEvent[L]>",
            str(ha.Event("TestEvent")))

        self.assertEqual(
            "<Event TestEvent[R]: beer=nice>",
            str(ha.Event("TestEvent",
                         {"beer": "nice"},
                         ha.EventOrigin.remote)))

    def test_as_dict(self):
        event_type = 'some_type'
        now = dt_util.utcnow()
        data = {'some': 'attr'}

        event = ha.Event(event_type, data, ha.EventOrigin.local, now)
        expected = {
            'event_type': event_type,
            'data': data,
            'origin': 'LOCAL',
            'time_fired': dt_util.datetime_to_str(now),
        }
        self.assertEqual(expected, event.as_dict())


class TestEventBus(unittest.TestCase):
    """ Test EventBus methods. """

    def setUp(self):     # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        self.bus = ha.EventBus(ha.create_worker_pool(0))
        self.bus.listen('test_event', lambda x: len)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.bus._pool.stop()

    def test_add_remove_listener(self):
        """ Test remove_listener method. """
        self.bus._pool.add_worker()
        old_count = len(self.bus.listeners)

        listener = lambda x: len

        self.bus.listen('test', listener)

        self.assertEqual(old_count + 1, len(self.bus.listeners))

        # Try deleting a non registered listener, nothing should happen
        self.bus.remove_listener('test', lambda x: len)

        # Remove listener
        self.bus.remove_listener('test', listener)
        self.assertEqual(old_count, len(self.bus.listeners))

        # Try deleting listener while category doesn't exist either
        self.bus.remove_listener('test', listener)

    def test_listen_once_event(self):
        """ Test listen_once_event method. """
        runs = []

        self.bus.listen_once('test_event', lambda x: runs.append(1))

        self.bus.fire('test_event')
        # Second time it should not increase runs
        self.bus.fire('test_event')

        self.bus._pool.add_worker()
        self.bus._pool.block_till_done()
        self.assertEqual(1, len(runs))


class TestState(unittest.TestCase):
    """ Test EventBus methods. """

    def test_init(self):
        """ Test state.init """
        self.assertRaises(
            InvalidEntityFormatError, ha.State,
            'invalid_entity_format', 'test_state')

    def test_domain(self):
        state = ha.State('some_domain.hello', 'world')
        self.assertEqual('some_domain', state.domain)

    def test_object_id(self):
        state = ha.State('domain.hello', 'world')
        self.assertEqual('hello', state.object_id)

    def test_name_if_no_friendly_name_attr(self):
        state = ha.State('domain.hello_world', 'world')
        self.assertEqual('hello world', state.name)

    def test_name_if_friendly_name_attr(self):
        name = 'Some Unique Name'
        state = ha.State('domain.hello_world', 'world',
                         {ATTR_FRIENDLY_NAME: name})
        self.assertEqual(name, state.name)

    def test_copy(self):
        state = ha.State('domain.hello', 'world', {'some': 'attr'})
        # Patch dt_util.utcnow() so we know last_updated got copied too
        with patch('homeassistant.core.dt_util.utcnow',
                   return_value=dt_util.utcnow() + timedelta(seconds=10)):
            copy = state.copy()
        self.assertEqual(state.entity_id, copy.entity_id)
        self.assertEqual(state.state, copy.state)
        self.assertEqual(state.attributes, copy.attributes)
        self.assertEqual(state.last_changed, copy.last_changed)
        self.assertEqual(state.last_updated, copy.last_updated)

    def test_dict_conversion(self):
        state = ha.State('domain.hello', 'world', {'some': 'attr'})
        self.assertEqual(state, ha.State.from_dict(state.as_dict()))

    def test_dict_conversion_with_wrong_data(self):
        self.assertIsNone(ha.State.from_dict(None))
        self.assertIsNone(ha.State.from_dict({'state': 'yes'}))
        self.assertIsNone(ha.State.from_dict({'entity_id': 'yes'}))

    def test_repr(self):
        """ Test state.repr """
        self.assertEqual("<state happy.happy=on @ 12:00:00 08-12-1984>",
                         str(ha.State(
                             "happy.happy", "on",
                             last_changed=datetime(1984, 12, 8, 12, 0, 0))))

        self.assertEqual(
            "<state happy.happy=on; brightness=144 @ 12:00:00 08-12-1984>",
            str(ha.State("happy.happy", "on", {"brightness": 144},
                         datetime(1984, 12, 8, 12, 0, 0))))


class TestStateMachine(unittest.TestCase):
    """ Test EventBus methods. """

    def setUp(self):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        self.pool = ha.create_worker_pool(0)
        self.bus = ha.EventBus(self.pool)
        self.states = ha.StateMachine(self.bus)
        self.states.set("light.Bowl", "on")
        self.states.set("switch.AC", "off")

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.pool.stop()

    def test_is_state(self):
        """ Test is_state method. """
        self.assertTrue(self.states.is_state('light.Bowl', 'on'))
        self.assertFalse(self.states.is_state('light.Bowl', 'off'))
        self.assertFalse(self.states.is_state('light.Non_existing', 'on'))

    def test_is_state_attr(self):
        """ Test is_state_attr method. """
        self.states.set("light.Bowl", "on", {"brightness": 100})
        self.assertTrue(
            self.states.is_state_attr('light.Bowl', 'brightness', 100))
        self.assertFalse(
            self.states.is_state_attr('light.Bowl', 'friendly_name', 200))
        self.assertFalse(
            self.states.is_state_attr('light.Bowl', 'friendly_name', 'Bowl'))
        self.assertFalse(
            self.states.is_state_attr('light.Non_existing', 'brightness', 100))

    def test_entity_ids(self):
        """ Test get_entity_ids method. """
        ent_ids = self.states.entity_ids()
        self.assertEqual(2, len(ent_ids))
        self.assertTrue('light.bowl' in ent_ids)
        self.assertTrue('switch.ac' in ent_ids)

        ent_ids = self.states.entity_ids('light')
        self.assertEqual(1, len(ent_ids))
        self.assertTrue('light.bowl' in ent_ids)

    def test_all(self):
        states = sorted(state.entity_id for state in self.states.all())
        self.assertEqual(['light.bowl', 'switch.ac'], states)

    def test_remove(self):
        """ Test remove method. """
        self.assertTrue('light.bowl' in self.states.entity_ids())
        self.assertTrue(self.states.remove('light.bowl'))
        self.assertFalse('light.bowl' in self.states.entity_ids())

        # If it does not exist, we should get False
        self.assertFalse(self.states.remove('light.Bowl'))

    def test_track_change(self):
        """ Test states.track_change. """
        self.pool.add_worker()

        # 2 lists to track how often our callbacks got called
        specific_runs = []
        wildcard_runs = []

        self.states.track_change(
            'light.Bowl', lambda a, b, c: specific_runs.append(1), 'on', 'off')

        self.states.track_change(
            'light.Bowl', lambda a, b, c: wildcard_runs.append(1),
            ha.MATCH_ALL, ha.MATCH_ALL)

        # Set same state should not trigger a state change/listener
        self.states.set('light.Bowl', 'on')
        self.bus._pool.block_till_done()
        self.assertEqual(0, len(specific_runs))
        self.assertEqual(0, len(wildcard_runs))

        # State change off -> on
        self.states.set('light.Bowl', 'off')
        self.bus._pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))

        # State change off -> off
        self.states.set('light.Bowl', 'off', {"some_attr": 1})
        self.bus._pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(2, len(wildcard_runs))

        # State change off -> on
        self.states.set('light.Bowl', 'on')
        self.bus._pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(3, len(wildcard_runs))

    def test_case_insensitivty(self):
        self.pool.add_worker()
        runs = []

        track_state_change(
            ha._MockHA(self.bus), 'light.BoWl', lambda a, b, c: runs.append(1),
            ha.MATCH_ALL, ha.MATCH_ALL)

        self.states.set('light.BOWL', 'off')
        self.bus._pool.block_till_done()

        self.assertTrue(self.states.is_state('light.bowl', 'off'))
        self.assertEqual(1, len(runs))

    def test_last_changed_not_updated_on_same_state(self):
        state = self.states.get('light.Bowl')

        future = dt_util.utcnow() + timedelta(hours=10)

        with patch('homeassistant.util.dt.utcnow', return_value=future):
            self.states.set("light.Bowl", "on", {'attr': 'triggers_change'})

        self.assertEqual(state.last_changed,
                         self.states.get('light.Bowl').last_changed)


class TestServiceCall(unittest.TestCase):
    """ Test ServiceCall class. """
    def test_repr(self):
        """ Test repr method. """
        self.assertEqual(
            "<ServiceCall homeassistant.start>",
            str(ha.ServiceCall('homeassistant', 'start')))

        self.assertEqual(
            "<ServiceCall homeassistant.start: fast=yes>",
            str(ha.ServiceCall('homeassistant', 'start', {"fast": "yes"})))


class TestServiceRegistry(unittest.TestCase):
    """ Test EventBus methods. """

    def setUp(self):     # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        self.pool = ha.create_worker_pool(0)
        self.bus = ha.EventBus(self.pool)
        self.services = ha.ServiceRegistry(self.bus, self.pool)
        self.services.register("test_domain", "test_service", lambda x: None)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        if self.pool.worker_count:
            self.pool.stop()

    def test_has_service(self):
        """ Test has_service method. """
        self.assertTrue(
            self.services.has_service("test_domain", "test_service"))
        self.assertFalse(
            self.services.has_service("test_domain", "non_existing"))
        self.assertFalse(
            self.services.has_service("non_existing", "test_service"))

    def test_services(self):
        expected = {
            'test_domain': {'test_service': {'description': '', 'fields': {}}}
        }
        self.assertEqual(expected, self.services.services)

    def test_call_with_blocking_done_in_time(self):
        self.pool.add_worker()
        self.pool.add_worker()
        calls = []
        self.services.register("test_domain", "register_calls",
                               lambda x: calls.append(1))

        self.assertTrue(
            self.services.call('test_domain', 'register_calls', blocking=True))
        self.assertEqual(1, len(calls))

    def test_call_with_blocking_not_done_in_time(self):
        calls = []
        self.services.register("test_domain", "register_calls",
                               lambda x: calls.append(1))

        orig_limit = ha.SERVICE_CALL_LIMIT
        ha.SERVICE_CALL_LIMIT = 0.01
        self.assertFalse(
            self.services.call('test_domain', 'register_calls', blocking=True))
        self.assertEqual(0, len(calls))
        ha.SERVICE_CALL_LIMIT = orig_limit

    def test_call_non_existing_with_blocking(self):
        self.pool.add_worker()
        self.pool.add_worker()
        orig_limit = ha.SERVICE_CALL_LIMIT
        ha.SERVICE_CALL_LIMIT = 0.01
        self.assertFalse(
            self.services.call('test_domain', 'i_do_not_exist', blocking=True))
        ha.SERVICE_CALL_LIMIT = orig_limit


class TestConfig(unittest.TestCase):
    def setUp(self):     # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        self.config = ha.Config()

    def test_config_dir_set_correct(self):
        """ Test config dir set correct. """
        data_dir = os.getenv('APPDATA') if os.name == "nt" \
            else os.path.expanduser('~')
        self.assertEqual(os.path.join(data_dir, ".homeassistant"),
                         self.config.config_dir)

    def test_path_with_file(self):
        """ Test get_config_path method. """
        data_dir = os.getenv('APPDATA') if os.name == "nt" \
            else os.path.expanduser('~')
        self.assertEqual(os.path.join(data_dir, ".homeassistant", "test.conf"),
                         self.config.path("test.conf"))

    def test_path_with_dir_and_file(self):
        """ Test get_config_path method. """
        data_dir = os.getenv('APPDATA') if os.name == "nt" \
            else os.path.expanduser('~')
        self.assertEqual(
            os.path.join(data_dir, ".homeassistant", "dir", "test.conf"),
            self.config.path("dir", "test.conf"))

    def test_temperature_not_convert_if_no_preference(self):
        """ No unit conversion to happen if no preference. """
        self.assertEqual(
            (25, TEMP_CELCIUS),
            self.config.temperature(25, TEMP_CELCIUS))
        self.assertEqual(
            (80, TEMP_FAHRENHEIT),
            self.config.temperature(80, TEMP_FAHRENHEIT))

    def test_temperature_not_convert_if_invalid_value(self):
        """ No unit conversion to happen if no preference. """
        self.config.temperature_unit = TEMP_FAHRENHEIT
        self.assertEqual(
            ('25a', TEMP_CELCIUS),
            self.config.temperature('25a', TEMP_CELCIUS))

    def test_temperature_not_convert_if_invalid_unit(self):
        """ No unit conversion to happen if no preference. """
        self.assertEqual(
            (25, 'Invalid unit'),
            self.config.temperature(25, 'Invalid unit'))

    def test_temperature_to_convert_to_celcius(self):
        self.config.temperature_unit = TEMP_CELCIUS

        self.assertEqual(
            (25, TEMP_CELCIUS),
            self.config.temperature(25, TEMP_CELCIUS))
        self.assertEqual(
            (26.7, TEMP_CELCIUS),
            self.config.temperature(80, TEMP_FAHRENHEIT))

    def test_temperature_to_convert_to_fahrenheit(self):
        self.config.temperature_unit = TEMP_FAHRENHEIT

        self.assertEqual(
            (77, TEMP_FAHRENHEIT),
            self.config.temperature(25, TEMP_CELCIUS))
        self.assertEqual(
            (80, TEMP_FAHRENHEIT),
            self.config.temperature(80, TEMP_FAHRENHEIT))

    def test_as_dict(self):
        expected = {
            'latitude': None,
            'longitude': None,
            'temperature_unit': None,
            'location_name': None,
            'time_zone': 'UTC',
            'components': [],
            'version': __version__,
        }

        self.assertEqual(expected, self.config.as_dict())


class TestWorkerPool(unittest.TestCase):
    def test_exception_during_job(self):
        pool = ha.create_worker_pool(1)

        def malicious_job(_):
            raise Exception("Test breaking worker pool")

        calls = []

        def register_call(_):
            calls.append(1)

        pool.add_job(ha.JobPriority.EVENT_DEFAULT, (malicious_job, None))
        pool.add_job(ha.JobPriority.EVENT_DEFAULT, (register_call, None))
        pool.block_till_done()
        self.assertEqual(1, len(calls))
