"""Test to verify that Home Assistant core works."""
# pylint: disable=protected-access
import asyncio
import logging
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from tempfile import TemporaryDirectory

import pytz
import pytest

import homeassistant.core as ha
from homeassistant.exceptions import (InvalidEntityFormatError,
                                      InvalidStateError)
from homeassistant.util.async_ import run_coroutine_threadsafe
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import (METRIC_SYSTEM)
from homeassistant.const import (
    __version__, EVENT_STATE_CHANGED, ATTR_FRIENDLY_NAME, CONF_UNIT_SYSTEM,
    ATTR_NOW, EVENT_TIME_CHANGED, EVENT_HOMEASSISTANT_STOP,
    EVENT_HOMEASSISTANT_CLOSE, EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED,
    EVENT_SERVICE_EXECUTED)

from tests.common import get_test_home_assistant, async_mock_service

PST = pytz.timezone('America/Los_Angeles')


def test_split_entity_id():
    """Test split_entity_id."""
    assert ha.split_entity_id('domain.object_id') == ['domain', 'object_id']


def test_async_add_job_schedule_callback():
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock()
    job = MagicMock()

    ha.HomeAssistant.async_add_job(hass, ha.callback(job))
    assert len(hass.loop.call_soon.mock_calls) == 1
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.add_job.mock_calls) == 0


@patch('asyncio.iscoroutinefunction', return_value=True)
def test_async_add_job_schedule_coroutinefunction(mock_iscoro):
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock()
    job = MagicMock()

    ha.HomeAssistant.async_add_job(hass, job)
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0


@patch('asyncio.iscoroutinefunction', return_value=False)
def test_async_add_job_add_threaded_job_to_pool(mock_iscoro):
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock()
    job = MagicMock()

    ha.HomeAssistant.async_add_job(hass, job)
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.loop.run_in_executor.mock_calls) == 1


@patch('asyncio.iscoroutine', return_value=True)
def test_async_create_task_schedule_coroutine(mock_iscoro):
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock()
    job = MagicMock()

    ha.HomeAssistant.async_create_task(hass, job)
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0


def test_async_run_job_calls_callback():
    """Test that the callback annotation is respected."""
    hass = MagicMock()
    calls = []

    def job():
        calls.append(1)

    ha.HomeAssistant.async_run_job(hass, ha.callback(job))
    assert len(calls) == 1
    assert len(hass.async_add_job.mock_calls) == 0


def test_async_run_job_delegates_non_async():
    """Test that the callback annotation is respected."""
    hass = MagicMock()
    calls = []

    def job():
        calls.append(1)

    ha.HomeAssistant.async_run_job(hass, job)
    assert len(calls) == 0
    assert len(hass.async_add_job.mock_calls) == 1


def test_stage_shutdown():
    """Simulate a shutdown, test calling stuff."""
    hass = get_test_home_assistant()
    test_stop = []
    test_close = []
    test_all = []

    hass.bus.listen(
        EVENT_HOMEASSISTANT_STOP, lambda event: test_stop.append(event))
    hass.bus.listen(
        EVENT_HOMEASSISTANT_CLOSE, lambda event: test_close.append(event))
    hass.bus.listen('*', lambda event: test_all.append(event))

    hass.stop()

    assert len(test_stop) == 1
    assert len(test_close) == 1
    assert len(test_all) == 1


class TestHomeAssistant(unittest.TestCase):
    """Test the Home Assistant core classes."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_pending_sheduler(self):
        """Add a coro to pending tasks."""
        call_count = []

        @asyncio.coroutine
        def test_coro():
            """Test Coro."""
            call_count.append('call')

        for _ in range(3):
            self.hass.add_job(test_coro())

        run_coroutine_threadsafe(
            asyncio.wait(self.hass._pending_tasks, loop=self.hass.loop),
            loop=self.hass.loop
        ).result()

        assert len(self.hass._pending_tasks) == 3
        assert len(call_count) == 3

    def test_async_add_job_pending_tasks_coro(self):
        """Add a coro to pending tasks."""
        call_count = []

        @asyncio.coroutine
        def test_coro():
            """Test Coro."""
            call_count.append('call')

        for _ in range(2):
            self.hass.add_job(test_coro())

        @asyncio.coroutine
        def wait_finish_callback():
            """Wait until all stuff is scheduled."""
            yield from asyncio.sleep(0, loop=self.hass.loop)
            yield from asyncio.sleep(0, loop=self.hass.loop)

        run_coroutine_threadsafe(
            wait_finish_callback(), self.hass.loop).result()

        assert len(self.hass._pending_tasks) == 2
        self.hass.block_till_done()
        assert len(call_count) == 2

    def test_async_add_job_pending_tasks_executor(self):
        """Run an executor in pending tasks."""
        call_count = []

        def test_executor():
            """Test executor."""
            call_count.append('call')

        @asyncio.coroutine
        def wait_finish_callback():
            """Wait until all stuff is scheduled."""
            yield from asyncio.sleep(0, loop=self.hass.loop)
            yield from asyncio.sleep(0, loop=self.hass.loop)

        for _ in range(2):
            self.hass.add_job(test_executor)

        run_coroutine_threadsafe(
            wait_finish_callback(), self.hass.loop).result()

        assert len(self.hass._pending_tasks) == 2
        self.hass.block_till_done()
        assert len(call_count) == 2

    def test_async_add_job_pending_tasks_callback(self):
        """Run a callback in pending tasks."""
        call_count = []

        @ha.callback
        def test_callback():
            """Test callback."""
            call_count.append('call')

        @asyncio.coroutine
        def wait_finish_callback():
            """Wait until all stuff is scheduled."""
            yield from asyncio.sleep(0, loop=self.hass.loop)
            yield from asyncio.sleep(0, loop=self.hass.loop)

        for _ in range(2):
            self.hass.add_job(test_callback)

        run_coroutine_threadsafe(
            wait_finish_callback(), self.hass.loop).result()

        self.hass.block_till_done()

        assert len(self.hass._pending_tasks) == 0
        assert len(call_count) == 2

    def test_add_job_with_none(self):
        """Try to add a job with None as function."""
        with pytest.raises(ValueError):
            self.hass.add_job(None, 'test_arg')


class TestEvent(unittest.TestCase):
    """A Test Event class."""

    def test_eq(self):
        """Test events."""
        now = dt_util.utcnow()
        data = {'some': 'attr'}
        context = ha.Context()
        event1, event2 = [
            ha.Event('some_type', data, time_fired=now, context=context)
            for _ in range(2)
        ]

        self.assertEqual(event1, event2)

    def test_repr(self):
        """Test that repr method works."""
        self.assertEqual(
            "<Event TestEvent[L]>",
            str(ha.Event("TestEvent")))

        self.assertEqual(
            "<Event TestEvent[R]: beer=nice>",
            str(ha.Event("TestEvent",
                         {"beer": "nice"},
                         ha.EventOrigin.remote)))

    def test_as_dict(self):
        """Test as dictionary."""
        event_type = 'some_type'
        now = dt_util.utcnow()
        data = {'some': 'attr'}

        event = ha.Event(event_type, data, ha.EventOrigin.local, now)
        expected = {
            'event_type': event_type,
            'data': data,
            'origin': 'LOCAL',
            'time_fired': now,
            'context': {
                'id': event.context.id,
                'user_id': event.context.user_id,
            },
        }
        self.assertEqual(expected, event.as_dict())


class TestEventBus(unittest.TestCase):
    """Test EventBus methods."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.bus = self.hass.bus

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop down stuff we started."""
        self.hass.stop()

    def test_add_remove_listener(self):
        """Test remove_listener method."""
        self.hass.allow_pool = False
        old_count = len(self.bus.listeners)

        def listener(_): pass

        unsub = self.bus.listen('test', listener)

        self.assertEqual(old_count + 1, len(self.bus.listeners))

        # Remove listener
        unsub()
        self.assertEqual(old_count, len(self.bus.listeners))

        # Should do nothing now
        unsub()

    def test_unsubscribe_listener(self):
        """Test unsubscribe listener from returned function."""
        calls = []

        @ha.callback
        def listener(event):
            """Mock listener."""
            calls.append(event)

        unsub = self.bus.listen('test', listener)

        self.bus.fire('test')
        self.hass.block_till_done()

        assert len(calls) == 1

        unsub()

        self.bus.fire('event')
        self.hass.block_till_done()

        assert len(calls) == 1

    def test_listen_once_event_with_callback(self):
        """Test listen_once_event method."""
        runs = []

        @ha.callback
        def event_handler(event):
            runs.append(event)

        self.bus.listen_once('test_event', event_handler)

        self.bus.fire('test_event')
        # Second time it should not increase runs
        self.bus.fire('test_event')

        self.hass.block_till_done()
        self.assertEqual(1, len(runs))

    def test_listen_once_event_with_coroutine(self):
        """Test listen_once_event method."""
        runs = []

        @asyncio.coroutine
        def event_handler(event):
            runs.append(event)

        self.bus.listen_once('test_event', event_handler)

        self.bus.fire('test_event')
        # Second time it should not increase runs
        self.bus.fire('test_event')

        self.hass.block_till_done()
        self.assertEqual(1, len(runs))

    def test_listen_once_event_with_thread(self):
        """Test listen_once_event method."""
        runs = []

        def event_handler(event):
            runs.append(event)

        self.bus.listen_once('test_event', event_handler)

        self.bus.fire('test_event')
        # Second time it should not increase runs
        self.bus.fire('test_event')

        self.hass.block_till_done()
        self.assertEqual(1, len(runs))

    def test_thread_event_listener(self):
        """Test thread event listener."""
        thread_calls = []

        def thread_listener(event):
            thread_calls.append(event)

        self.bus.listen('test_thread', thread_listener)
        self.bus.fire('test_thread')
        self.hass.block_till_done()
        assert len(thread_calls) == 1

    def test_callback_event_listener(self):
        """Test callback event listener."""
        callback_calls = []

        @ha.callback
        def callback_listener(event):
            callback_calls.append(event)

        self.bus.listen('test_callback', callback_listener)
        self.bus.fire('test_callback')
        self.hass.block_till_done()
        assert len(callback_calls) == 1

    def test_coroutine_event_listener(self):
        """Test coroutine event listener."""
        coroutine_calls = []

        @asyncio.coroutine
        def coroutine_listener(event):
            coroutine_calls.append(event)

        self.bus.listen('test_coroutine', coroutine_listener)
        self.bus.fire('test_coroutine')
        self.hass.block_till_done()
        assert len(coroutine_calls) == 1


class TestState(unittest.TestCase):
    """Test State methods."""

    def test_init(self):
        """Test state.init."""
        self.assertRaises(
            InvalidEntityFormatError, ha.State,
            'invalid_entity_format', 'test_state')

        self.assertRaises(
            InvalidStateError, ha.State,
            'domain.long_state', 't' * 256)

    def test_domain(self):
        """Test domain."""
        state = ha.State('some_domain.hello', 'world')
        self.assertEqual('some_domain', state.domain)

    def test_object_id(self):
        """Test object ID."""
        state = ha.State('domain.hello', 'world')
        self.assertEqual('hello', state.object_id)

    def test_name_if_no_friendly_name_attr(self):
        """Test if there is no friendly name."""
        state = ha.State('domain.hello_world', 'world')
        self.assertEqual('hello world', state.name)

    def test_name_if_friendly_name_attr(self):
        """Test if there is a friendly name."""
        name = 'Some Unique Name'
        state = ha.State('domain.hello_world', 'world',
                         {ATTR_FRIENDLY_NAME: name})
        self.assertEqual(name, state.name)

    def test_dict_conversion(self):
        """Test conversion of dict."""
        state = ha.State('domain.hello', 'world', {'some': 'attr'})
        self.assertEqual(state, ha.State.from_dict(state.as_dict()))

    def test_dict_conversion_with_wrong_data(self):
        """Test conversion with wrong data."""
        self.assertIsNone(ha.State.from_dict(None))
        self.assertIsNone(ha.State.from_dict({'state': 'yes'}))
        self.assertIsNone(ha.State.from_dict({'entity_id': 'yes'}))

    def test_repr(self):
        """Test state.repr."""
        self.assertEqual("<state happy.happy=on @ 1984-12-08T12:00:00+00:00>",
                         str(ha.State(
                             "happy.happy", "on",
                             last_changed=datetime(1984, 12, 8, 12, 0, 0))))

        self.assertEqual(
            "<state happy.happy=on; brightness=144 @ "
            "1984-12-08T12:00:00+00:00>",
            str(ha.State("happy.happy", "on", {"brightness": 144},
                         datetime(1984, 12, 8, 12, 0, 0))))


class TestStateMachine(unittest.TestCase):
    """Test State machine methods."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.states = self.hass.states
        self.states.set("light.Bowl", "on")
        self.states.set("switch.AC", "off")

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop down stuff we started."""
        self.hass.stop()

    def test_is_state(self):
        """Test is_state method."""
        self.assertTrue(self.states.is_state('light.Bowl', 'on'))
        self.assertFalse(self.states.is_state('light.Bowl', 'off'))
        self.assertFalse(self.states.is_state('light.Non_existing', 'on'))

    def test_entity_ids(self):
        """Test get_entity_ids method."""
        ent_ids = self.states.entity_ids()
        self.assertEqual(2, len(ent_ids))
        self.assertTrue('light.bowl' in ent_ids)
        self.assertTrue('switch.ac' in ent_ids)

        ent_ids = self.states.entity_ids('light')
        self.assertEqual(1, len(ent_ids))
        self.assertTrue('light.bowl' in ent_ids)

    def test_all(self):
        """Test everything."""
        states = sorted(state.entity_id for state in self.states.all())
        self.assertEqual(['light.bowl', 'switch.ac'], states)

    def test_remove(self):
        """Test remove method."""
        events = []

        @ha.callback
        def callback(event):
            events.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        self.assertIn('light.bowl', self.states.entity_ids())
        self.assertTrue(self.states.remove('light.bowl'))
        self.hass.block_till_done()

        self.assertNotIn('light.bowl', self.states.entity_ids())
        self.assertEqual(1, len(events))
        self.assertEqual('light.bowl', events[0].data.get('entity_id'))
        self.assertIsNotNone(events[0].data.get('old_state'))
        self.assertEqual('light.bowl', events[0].data['old_state'].entity_id)
        self.assertIsNone(events[0].data.get('new_state'))

        # If it does not exist, we should get False
        self.assertFalse(self.states.remove('light.Bowl'))
        self.hass.block_till_done()
        self.assertEqual(1, len(events))

    def test_case_insensitivty(self):
        """Test insensitivty."""
        runs = []

        @ha.callback
        def callback(event):
            runs.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        self.states.set('light.BOWL', 'off')
        self.hass.block_till_done()

        self.assertTrue(self.states.is_state('light.bowl', 'off'))
        self.assertEqual(1, len(runs))

    def test_last_changed_not_updated_on_same_state(self):
        """Test to not update the existing, same state."""
        state = self.states.get('light.Bowl')

        future = dt_util.utcnow() + timedelta(hours=10)

        with patch('homeassistant.util.dt.utcnow', return_value=future):
            self.states.set("light.Bowl", "on", {'attr': 'triggers_change'})
            self.hass.block_till_done()

        state2 = self.states.get('light.Bowl')
        assert state2 is not None
        assert state.last_changed == state2.last_changed

    def test_force_update(self):
        """Test force update option."""
        events = []

        @ha.callback
        def callback(event):
            events.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        self.states.set('light.bowl', 'on')
        self.hass.block_till_done()
        self.assertEqual(0, len(events))

        self.states.set('light.bowl', 'on', None, True)
        self.hass.block_till_done()
        self.assertEqual(1, len(events))


def test_service_call_repr():
    """Test ServiceCall repr."""
    call = ha.ServiceCall('homeassistant', 'start')
    assert str(call) == \
        "<ServiceCall homeassistant.start (c:{})>".format(call.context.id)

    call2 = ha.ServiceCall('homeassistant', 'start', {'fast': 'yes'})
    assert str(call2) == \
        "<ServiceCall homeassistant.start (c:{}): fast=yes>".format(
            call2.context.id)


class TestServiceRegistry(unittest.TestCase):
    """Test ServicerRegistry methods."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.services = self.hass.services

        @ha.callback
        def mock_service(call):
            pass

        self.services.register("Test_Domain", "TEST_SERVICE", mock_service)

        self.calls_register = []

        @ha.callback
        def mock_event_register(event):
            """Mock register event."""
            self.calls_register.append(event)

        self.hass.bus.listen(EVENT_SERVICE_REGISTERED, mock_event_register)

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop down stuff we started."""
        self.hass.stop()

    def test_has_service(self):
        """Test has_service method."""
        self.assertTrue(
            self.services.has_service("tesT_domaiN", "tesT_servicE"))
        self.assertFalse(
            self.services.has_service("test_domain", "non_existing"))
        self.assertFalse(
            self.services.has_service("non_existing", "test_service"))

    def test_services(self):
        """Test services."""
        assert len(self.services.services) == 1

    def test_call_with_blocking_done_in_time(self):
        """Test call with blocking."""
        calls = []

        @ha.callback
        def service_handler(call):
            """Service handler."""
            calls.append(call)

        self.services.register(
            "test_domain", "register_calls", service_handler)
        self.hass.block_till_done()

        assert len(self.calls_register) == 1
        assert self.calls_register[-1].data['domain'] == 'test_domain'
        assert self.calls_register[-1].data['service'] == 'register_calls'

        self.assertTrue(
            self.services.call('test_domain', 'REGISTER_CALLS', blocking=True))
        self.assertEqual(1, len(calls))

    def test_call_non_existing_with_blocking(self):
        """Test non-existing with blocking."""
        prior = ha.SERVICE_CALL_LIMIT
        try:
            ha.SERVICE_CALL_LIMIT = 0.01
            assert not self.services.call('test_domain', 'i_do_not_exist',
                                          blocking=True)
        finally:
            ha.SERVICE_CALL_LIMIT = prior

    def test_async_service(self):
        """Test registering and calling an async service."""
        calls = []

        @asyncio.coroutine
        def service_handler(call):
            """Service handler coroutine."""
            calls.append(call)

        self.services.register(
            'test_domain', 'register_calls', service_handler)
        self.hass.block_till_done()

        assert len(self.calls_register) == 1
        assert self.calls_register[-1].data['domain'] == 'test_domain'
        assert self.calls_register[-1].data['service'] == 'register_calls'

        self.assertTrue(
            self.services.call('test_domain', 'REGISTER_CALLS', blocking=True))
        self.hass.block_till_done()
        self.assertEqual(1, len(calls))

    def test_callback_service(self):
        """Test registering and calling an async service."""
        calls = []

        @ha.callback
        def service_handler(call):
            """Service handler coroutine."""
            calls.append(call)

        self.services.register(
            'test_domain', 'register_calls', service_handler)
        self.hass.block_till_done()

        assert len(self.calls_register) == 1
        assert self.calls_register[-1].data['domain'] == 'test_domain'
        assert self.calls_register[-1].data['service'] == 'register_calls'

        self.assertTrue(
            self.services.call('test_domain', 'REGISTER_CALLS', blocking=True))
        self.hass.block_till_done()
        self.assertEqual(1, len(calls))

    def test_remove_service(self):
        """Test remove service."""
        calls_remove = []

        @ha.callback
        def mock_event_remove(event):
            """Mock register event."""
            calls_remove.append(event)

        self.hass.bus.listen(EVENT_SERVICE_REMOVED, mock_event_remove)

        assert self.services.has_service('test_Domain', 'test_Service')

        self.services.remove('test_Domain', 'test_Service')
        self.hass.block_till_done()

        assert not self.services.has_service('test_Domain', 'test_Service')
        assert len(calls_remove) == 1
        assert calls_remove[-1].data['domain'] == 'test_domain'
        assert calls_remove[-1].data['service'] == 'test_service'

    def test_remove_service_that_not_exists(self):
        """Test remove service that not exists."""
        calls_remove = []

        @ha.callback
        def mock_event_remove(event):
            """Mock register event."""
            calls_remove.append(event)

        self.hass.bus.listen(EVENT_SERVICE_REMOVED, mock_event_remove)

        assert not self.services.has_service('test_xxx', 'test_yyy')
        self.services.remove('test_xxx', 'test_yyy')
        self.hass.block_till_done()
        assert len(calls_remove) == 0


class TestConfig(unittest.TestCase):
    """Test configuration methods."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.config = ha.Config()
        self.assertIsNone(self.config.config_dir)

    def test_path_with_file(self):
        """Test get_config_path method."""
        self.config.config_dir = '/tmp/ha-config'
        self.assertEqual("/tmp/ha-config/test.conf",
                         self.config.path("test.conf"))

    def test_path_with_dir_and_file(self):
        """Test get_config_path method."""
        self.config.config_dir = '/tmp/ha-config'
        self.assertEqual("/tmp/ha-config/dir/test.conf",
                         self.config.path("dir", "test.conf"))

    def test_as_dict(self):
        """Test as dict."""
        self.config.config_dir = '/tmp/ha-config'
        expected = {
            'latitude': None,
            'longitude': None,
            'elevation': None,
            CONF_UNIT_SYSTEM: METRIC_SYSTEM.as_dict(),
            'location_name': None,
            'time_zone': 'UTC',
            'components': set(),
            'config_dir': '/tmp/ha-config',
            'whitelist_external_dirs': set(),
            'version': __version__,
        }

        self.assertEqual(expected, self.config.as_dict())

    def test_is_allowed_path(self):
        """Test is_allowed_path method."""
        with TemporaryDirectory() as tmp_dir:
            # The created dir is in /tmp. This is a symlink on OS X
            # causing this test to fail unless we resolve path first.
            self.config.whitelist_external_dirs = set((
                os.path.realpath(tmp_dir),
            ))

            test_file = os.path.join(tmp_dir, "test.jpg")
            with open(test_file, "w") as tmp_file:
                tmp_file.write("test")

            valid = [
                test_file,
                tmp_dir,
                os.path.join(tmp_dir, 'notfound321')
            ]
            for path in valid:
                assert self.config.is_allowed_path(path)

            self.config.whitelist_external_dirs = set(('/home', '/var'))

            unvalid = [
                "/hass/config/secure",
                "/etc/passwd",
                "/root/secure_file",
                "/var/../etc/passwd",
                test_file,
            ]
            for path in unvalid:
                assert not self.config.is_allowed_path(path)

            with self.assertRaises(AssertionError):
                self.config.is_allowed_path(None)


@patch('homeassistant.core.monotonic')
def test_create_timer(mock_monotonic, loop):
    """Test create timer."""
    hass = MagicMock()
    funcs = []
    orig_callback = ha.callback

    def mock_callback(func):
        funcs.append(func)
        return orig_callback(func)

    mock_monotonic.side_effect = 10.2, 10.8, 11.3

    with patch.object(ha, 'callback', mock_callback), \
            patch('homeassistant.core.dt_util.utcnow',
                  return_value=datetime(2018, 12, 31, 3, 4, 5, 333333)):
        ha._async_create_timer(hass)

    assert len(funcs) == 2
    fire_time_event, stop_timer = funcs

    assert len(hass.loop.call_later.mock_calls) == 1
    delay, callback, target = hass.loop.call_later.mock_calls[0][1]
    assert abs(delay - 0.666667) < 0.001
    assert callback is fire_time_event
    assert abs(target - 10.866667) < 0.001

    with patch('homeassistant.core.dt_util.utcnow',
               return_value=datetime(2018, 12, 31, 3, 4, 6, 100000)):
        callback(target)

    assert len(hass.bus.async_listen_once.mock_calls) == 1
    assert len(hass.bus.async_fire.mock_calls) == 1
    assert len(hass.loop.call_later.mock_calls) == 2

    event_type, callback = hass.bus.async_listen_once.mock_calls[0][1]
    assert event_type == EVENT_HOMEASSISTANT_STOP
    assert callback is stop_timer

    delay, callback, target = hass.loop.call_later.mock_calls[1][1]
    assert abs(delay - 0.9) < 0.001
    assert callback is fire_time_event
    assert abs(target - 12.2) < 0.001

    event_type, event_data = hass.bus.async_fire.mock_calls[0][1]
    assert event_type == EVENT_TIME_CHANGED
    assert event_data[ATTR_NOW] == datetime(2018, 12, 31, 3, 4, 6, 100000)


@patch('homeassistant.core.monotonic')
def test_timer_out_of_sync(mock_monotonic, loop):
    """Test create timer."""
    hass = MagicMock()
    funcs = []
    orig_callback = ha.callback

    def mock_callback(func):
        funcs.append(func)
        return orig_callback(func)

    mock_monotonic.side_effect = 10.2, 13.3, 13.4

    with patch.object(ha, 'callback', mock_callback), \
            patch('homeassistant.core.dt_util.utcnow',
                  return_value=datetime(2018, 12, 31, 3, 4, 5, 333333)):
        ha._async_create_timer(hass)

    delay, callback, target = hass.loop.call_later.mock_calls[0][1]

    with patch.object(ha, '_LOGGER', MagicMock()) as mock_logger, \
            patch('homeassistant.core.dt_util.utcnow',
                  return_value=datetime(2018, 12, 31, 3, 4, 8, 200000)):
        callback(target)

        assert len(mock_logger.error.mock_calls) == 1

        assert len(funcs) == 2
        fire_time_event, stop_timer = funcs

    assert len(hass.loop.call_later.mock_calls) == 2

    delay, callback, target = hass.loop.call_later.mock_calls[1][1]
    assert abs(delay - 0.8) < 0.001
    assert callback is fire_time_event
    assert abs(target - 14.2) < 0.001


@asyncio.coroutine
def test_hass_start_starts_the_timer(loop):
    """Test when hass starts, it starts the timer."""
    hass = ha.HomeAssistant(loop=loop)

    try:
        with patch('homeassistant.core._async_create_timer') as mock_timer:
            yield from hass.async_start()

        assert hass.state == ha.CoreState.running
        assert not hass._track_task
        assert len(mock_timer.mock_calls) == 1
        assert mock_timer.mock_calls[0][1][0] is hass

    finally:
        yield from hass.async_stop()
        assert hass.state == ha.CoreState.not_running


@asyncio.coroutine
def test_start_taking_too_long(loop, caplog):
    """Test when async_start takes too long."""
    hass = ha.HomeAssistant(loop=loop)
    caplog.set_level(logging.WARNING)

    try:
        with patch('homeassistant.core.timeout',
                   side_effect=asyncio.TimeoutError), \
             patch('homeassistant.core._async_create_timer') as mock_timer:
            yield from hass.async_start()

        assert hass.state == ha.CoreState.running
        assert len(mock_timer.mock_calls) == 1
        assert mock_timer.mock_calls[0][1][0] is hass
        assert 'Something is blocking Home Assistant' in caplog.text

    finally:
        yield from hass.async_stop()
        assert hass.state == ha.CoreState.not_running


@asyncio.coroutine
def test_track_task_functions(loop):
    """Test function to start/stop track task and initial state."""
    hass = ha.HomeAssistant(loop=loop)
    try:
        assert hass._track_task

        hass.async_stop_track_tasks()
        assert not hass._track_task

        hass.async_track_tasks()
        assert hass._track_task
    finally:
        yield from hass.async_stop()


async def test_service_executed_with_subservices(hass):
    """Test we block correctly till all services done."""
    calls = async_mock_service(hass, 'test', 'inner')

    async def handle_outer(call):
        """Handle outer service call."""
        calls.append(call)
        call1 = hass.services.async_call('test', 'inner', blocking=True,
                                         context=call.context)
        call2 = hass.services.async_call('test', 'inner', blocking=True,
                                         context=call.context)
        await asyncio.wait([call1, call2])
        calls.append(call)

    hass.services.async_register('test', 'outer', handle_outer)

    await hass.services.async_call('test', 'outer', blocking=True)

    assert len(calls) == 4
    assert [call.service for call in calls] == [
        'outer', 'inner', 'inner', 'outer']
    assert len(hass.bus.async_listeners().get(EVENT_SERVICE_EXECUTED, [])) == 0
