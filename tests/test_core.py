"""Test to verify that Home Assistant core works."""
# pylint: disable=protected-access
import asyncio
from datetime import datetime, timedelta
import functools
import logging
import os
from tempfile import TemporaryDirectory
import unittest

import pytest
import pytz
import voluptuous as vol

from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_NOW,
    ATTR_SECONDS,
    CONF_UNIT_SYSTEM,
    EVENT_CALL_SERVICE,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_STATE_CHANGED,
    EVENT_TIME_CHANGED,
    EVENT_TIMER_OUT_OF_SYNC,
    MATCH_ALL,
    __version__,
)
import homeassistant.core as ha
from homeassistant.exceptions import InvalidEntityFormatError, InvalidStateError
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.async_mock import MagicMock, Mock, PropertyMock, patch
from tests.common import async_mock_service, get_test_home_assistant

PST = pytz.timezone("America/Los_Angeles")


def test_split_entity_id():
    """Test split_entity_id."""
    assert ha.split_entity_id("domain.object_id") == ["domain", "object_id"]


def test_async_add_job_schedule_callback():
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock()
    job = MagicMock()

    ha.HomeAssistant.async_add_job(hass, ha.callback(job))
    assert len(hass.loop.call_soon.mock_calls) == 1
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.add_job.mock_calls) == 0


def test_async_add_job_schedule_partial_callback():
    """Test that we schedule partial coros and add jobs to the job pool."""
    hass = MagicMock()
    job = MagicMock()
    partial = functools.partial(ha.callback(job))

    ha.HomeAssistant.async_add_job(hass, partial)
    assert len(hass.loop.call_soon.mock_calls) == 1
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.add_job.mock_calls) == 0


def test_async_add_job_schedule_coroutinefunction(loop):
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=loop))

    async def job():
        pass

    ha.HomeAssistant.async_add_job(hass, job)
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0


def test_async_add_job_schedule_partial_coroutinefunction(loop):
    """Test that we schedule partial coros and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=loop))

    async def job():
        pass

    partial = functools.partial(job)

    ha.HomeAssistant.async_add_job(hass, partial)
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0


def test_async_add_job_add_threaded_job_to_pool():
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock()

    def job():
        pass

    ha.HomeAssistant.async_add_job(hass, job)
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.loop.run_in_executor.mock_calls) == 1


def test_async_create_task_schedule_coroutine(loop):
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=loop))

    async def job():
        pass

    ha.HomeAssistant.async_create_task(hass, job())
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
    test_final_write = []
    test_close = []
    test_all = []

    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, lambda event: test_stop.append(event))
    hass.bus.listen(
        EVENT_HOMEASSISTANT_FINAL_WRITE, lambda event: test_final_write.append(event)
    )
    hass.bus.listen(EVENT_HOMEASSISTANT_CLOSE, lambda event: test_close.append(event))
    hass.bus.listen("*", lambda event: test_all.append(event))

    hass.stop()

    assert len(test_stop) == 1
    assert len(test_close) == 1
    assert len(test_final_write) == 1
    assert len(test_all) == 2


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
            call_count.append("call")

        for _ in range(3):
            self.hass.add_job(test_coro())

        asyncio.run_coroutine_threadsafe(
            asyncio.wait(self.hass._pending_tasks), loop=self.hass.loop
        ).result()

        assert len(self.hass._pending_tasks) == 3
        assert len(call_count) == 3

    def test_async_add_job_pending_tasks_coro(self):
        """Add a coro to pending tasks."""
        call_count = []

        @asyncio.coroutine
        def test_coro():
            """Test Coro."""
            call_count.append("call")

        for _ in range(2):
            self.hass.add_job(test_coro())

        @asyncio.coroutine
        def wait_finish_callback():
            """Wait until all stuff is scheduled."""
            yield from asyncio.sleep(0)
            yield from asyncio.sleep(0)

        asyncio.run_coroutine_threadsafe(
            wait_finish_callback(), self.hass.loop
        ).result()

        assert len(self.hass._pending_tasks) == 2
        self.hass.block_till_done()
        assert len(call_count) == 2

    def test_async_add_job_pending_tasks_executor(self):
        """Run an executor in pending tasks."""
        call_count = []

        def test_executor():
            """Test executor."""
            call_count.append("call")

        @asyncio.coroutine
        def wait_finish_callback():
            """Wait until all stuff is scheduled."""
            yield from asyncio.sleep(0)
            yield from asyncio.sleep(0)

        for _ in range(2):
            self.hass.add_job(test_executor)

        asyncio.run_coroutine_threadsafe(
            wait_finish_callback(), self.hass.loop
        ).result()

        assert len(self.hass._pending_tasks) == 2
        self.hass.block_till_done()
        assert len(call_count) == 2

    def test_async_add_job_pending_tasks_callback(self):
        """Run a callback in pending tasks."""
        call_count = []

        @ha.callback
        def test_callback():
            """Test callback."""
            call_count.append("call")

        @asyncio.coroutine
        def wait_finish_callback():
            """Wait until all stuff is scheduled."""
            yield from asyncio.sleep(0)
            yield from asyncio.sleep(0)

        for _ in range(2):
            self.hass.add_job(test_callback)

        asyncio.run_coroutine_threadsafe(
            wait_finish_callback(), self.hass.loop
        ).result()

        self.hass.block_till_done()

        assert len(self.hass._pending_tasks) == 0
        assert len(call_count) == 2

    def test_add_job_with_none(self):
        """Try to add a job with None as function."""
        with pytest.raises(ValueError):
            self.hass.add_job(None, "test_arg")


class TestEvent(unittest.TestCase):
    """A Test Event class."""

    def test_eq(self):
        """Test events."""
        now = dt_util.utcnow()
        data = {"some": "attr"}
        context = ha.Context()
        event1, event2 = [
            ha.Event("some_type", data, time_fired=now, context=context)
            for _ in range(2)
        ]

        assert event1 == event2

    def test_repr(self):
        """Test that repr method works."""
        assert str(ha.Event("TestEvent")) == "<Event TestEvent[L]>"

        assert (
            str(ha.Event("TestEvent", {"beer": "nice"}, ha.EventOrigin.remote))
            == "<Event TestEvent[R]: beer=nice>"
        )

    def test_as_dict(self):
        """Test as dictionary."""
        event_type = "some_type"
        now = dt_util.utcnow()
        data = {"some": "attr"}

        event = ha.Event(event_type, data, ha.EventOrigin.local, now)
        expected = {
            "event_type": event_type,
            "data": data,
            "origin": "LOCAL",
            "time_fired": now,
            "context": {
                "id": event.context.id,
                "parent_id": None,
                "user_id": event.context.user_id,
            },
        }
        assert expected == event.as_dict()


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

        def listener(_):
            pass

        unsub = self.bus.listen("test", listener)

        assert old_count + 1 == len(self.bus.listeners)

        # Remove listener
        unsub()
        assert old_count == len(self.bus.listeners)

        # Should do nothing now
        unsub()

    def test_unsubscribe_listener(self):
        """Test unsubscribe listener from returned function."""
        calls = []

        @ha.callback
        def listener(event):
            """Mock listener."""
            calls.append(event)

        unsub = self.bus.listen("test", listener)

        self.bus.fire("test")
        self.hass.block_till_done()

        assert len(calls) == 1

        unsub()

        self.bus.fire("event")
        self.hass.block_till_done()

        assert len(calls) == 1

    def test_listen_once_event_with_callback(self):
        """Test listen_once_event method."""
        runs = []

        @ha.callback
        def event_handler(event):
            runs.append(event)

        self.bus.listen_once("test_event", event_handler)

        self.bus.fire("test_event")
        # Second time it should not increase runs
        self.bus.fire("test_event")

        self.hass.block_till_done()
        assert len(runs) == 1

    def test_listen_once_event_with_coroutine(self):
        """Test listen_once_event method."""
        runs = []

        @asyncio.coroutine
        def event_handler(event):
            runs.append(event)

        self.bus.listen_once("test_event", event_handler)

        self.bus.fire("test_event")
        # Second time it should not increase runs
        self.bus.fire("test_event")

        self.hass.block_till_done()
        assert len(runs) == 1

    def test_listen_once_event_with_thread(self):
        """Test listen_once_event method."""
        runs = []

        def event_handler(event):
            runs.append(event)

        self.bus.listen_once("test_event", event_handler)

        self.bus.fire("test_event")
        # Second time it should not increase runs
        self.bus.fire("test_event")

        self.hass.block_till_done()
        assert len(runs) == 1

    def test_thread_event_listener(self):
        """Test thread event listener."""
        thread_calls = []

        def thread_listener(event):
            thread_calls.append(event)

        self.bus.listen("test_thread", thread_listener)
        self.bus.fire("test_thread")
        self.hass.block_till_done()
        assert len(thread_calls) == 1

    def test_callback_event_listener(self):
        """Test callback event listener."""
        callback_calls = []

        @ha.callback
        def callback_listener(event):
            callback_calls.append(event)

        self.bus.listen("test_callback", callback_listener)
        self.bus.fire("test_callback")
        self.hass.block_till_done()
        assert len(callback_calls) == 1

    def test_coroutine_event_listener(self):
        """Test coroutine event listener."""
        coroutine_calls = []

        @asyncio.coroutine
        def coroutine_listener(event):
            coroutine_calls.append(event)

        self.bus.listen("test_coroutine", coroutine_listener)
        self.bus.fire("test_coroutine")
        self.hass.block_till_done()
        assert len(coroutine_calls) == 1


def test_state_init():
    """Test state.init."""
    with pytest.raises(InvalidEntityFormatError):
        ha.State("invalid_entity_format", "test_state")

    with pytest.raises(InvalidStateError):
        ha.State("domain.long_state", "t" * 256)


def test_state_domain():
    """Test domain."""
    state = ha.State("some_domain.hello", "world")
    assert state.domain == "some_domain"


def test_state_object_id():
    """Test object ID."""
    state = ha.State("domain.hello", "world")
    assert state.object_id == "hello"


def test_state_name_if_no_friendly_name_attr():
    """Test if there is no friendly name."""
    state = ha.State("domain.hello_world", "world")
    assert state.name == "hello world"


def test_state_name_if_friendly_name_attr():
    """Test if there is a friendly name."""
    name = "Some Unique Name"
    state = ha.State("domain.hello_world", "world", {ATTR_FRIENDLY_NAME: name})
    assert state.name == name


def test_state_dict_conversion():
    """Test conversion of dict."""
    state = ha.State("domain.hello", "world", {"some": "attr"})
    assert state == ha.State.from_dict(state.as_dict())


def test_state_dict_conversion_with_wrong_data():
    """Test conversion with wrong data."""
    assert ha.State.from_dict(None) is None
    assert ha.State.from_dict({"state": "yes"}) is None
    assert ha.State.from_dict({"entity_id": "yes"}) is None
    # Make sure invalid context data doesn't crash
    wrong_context = ha.State.from_dict(
        {
            "entity_id": "light.kitchen",
            "state": "on",
            "context": {"id": "123", "non-existing": "crash"},
        }
    )
    assert wrong_context is not None
    assert wrong_context.context.id == "123"


def test_state_repr():
    """Test state.repr."""
    assert (
        str(ha.State("happy.happy", "on", last_changed=datetime(1984, 12, 8, 12, 0, 0)))
        == "<state happy.happy=on @ 1984-12-08T12:00:00+00:00>"
    )

    assert (
        str(
            ha.State(
                "happy.happy",
                "on",
                {"brightness": 144},
                datetime(1984, 12, 8, 12, 0, 0),
            )
        )
        == "<state happy.happy=on; brightness=144 @ "
        "1984-12-08T12:00:00+00:00>"
    )


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
        assert self.states.is_state("light.Bowl", "on")
        assert not self.states.is_state("light.Bowl", "off")
        assert not self.states.is_state("light.Non_existing", "on")

    def test_entity_ids(self):
        """Test get_entity_ids method."""
        ent_ids = self.states.entity_ids()
        assert len(ent_ids) == 2
        assert "light.bowl" in ent_ids
        assert "switch.ac" in ent_ids

        ent_ids = self.states.entity_ids("light")
        assert len(ent_ids) == 1
        assert "light.bowl" in ent_ids

    def test_all(self):
        """Test everything."""
        states = sorted(state.entity_id for state in self.states.all())
        assert ["light.bowl", "switch.ac"] == states

    def test_remove(self):
        """Test remove method."""
        events = []

        @ha.callback
        def callback(event):
            events.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        assert "light.bowl" in self.states.entity_ids()
        assert self.states.remove("light.bowl")
        self.hass.block_till_done()

        assert "light.bowl" not in self.states.entity_ids()
        assert len(events) == 1
        assert events[0].data.get("entity_id") == "light.bowl"
        assert events[0].data.get("old_state") is not None
        assert events[0].data["old_state"].entity_id == "light.bowl"
        assert events[0].data.get("new_state") is None

        # If it does not exist, we should get False
        assert not self.states.remove("light.Bowl")
        self.hass.block_till_done()
        assert len(events) == 1

    def test_case_insensitivty(self):
        """Test insensitivty."""
        runs = []

        @ha.callback
        def callback(event):
            runs.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        self.states.set("light.BOWL", "off")
        self.hass.block_till_done()

        assert self.states.is_state("light.bowl", "off")
        assert len(runs) == 1

    def test_last_changed_not_updated_on_same_state(self):
        """Test to not update the existing, same state."""
        state = self.states.get("light.Bowl")

        future = dt_util.utcnow() + timedelta(hours=10)

        with patch("homeassistant.util.dt.utcnow", return_value=future):
            self.states.set("light.Bowl", "on", {"attr": "triggers_change"})
            self.hass.block_till_done()

        state2 = self.states.get("light.Bowl")
        assert state2 is not None
        assert state.last_changed == state2.last_changed

    def test_force_update(self):
        """Test force update option."""
        events = []

        @ha.callback
        def callback(event):
            events.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        self.states.set("light.bowl", "on")
        self.hass.block_till_done()
        assert len(events) == 0

        self.states.set("light.bowl", "on", None, True)
        self.hass.block_till_done()
        assert len(events) == 1


def test_service_call_repr():
    """Test ServiceCall repr."""
    call = ha.ServiceCall("homeassistant", "start")
    assert str(call) == f"<ServiceCall homeassistant.start (c:{call.context.id})>"

    call2 = ha.ServiceCall("homeassistant", "start", {"fast": "yes"})
    assert (
        str(call2)
        == f"<ServiceCall homeassistant.start (c:{call2.context.id}): fast=yes>"
    )


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
        assert self.services.has_service("tesT_domaiN", "tesT_servicE")
        assert not self.services.has_service("test_domain", "non_existing")
        assert not self.services.has_service("non_existing", "test_service")

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

        self.services.register("test_domain", "register_calls", service_handler)
        self.hass.block_till_done()

        assert len(self.calls_register) == 1
        assert self.calls_register[-1].data["domain"] == "test_domain"
        assert self.calls_register[-1].data["service"] == "register_calls"

        assert self.services.call("test_domain", "REGISTER_CALLS", blocking=True)
        assert len(calls) == 1

    def test_call_non_existing_with_blocking(self):
        """Test non-existing with blocking."""
        with pytest.raises(ha.ServiceNotFound):
            self.services.call("test_domain", "i_do_not_exist", blocking=True)

    def test_async_service(self):
        """Test registering and calling an async service."""
        calls = []

        async def service_handler(call):
            """Service handler coroutine."""
            calls.append(call)

        self.services.register("test_domain", "register_calls", service_handler)
        self.hass.block_till_done()

        assert len(self.calls_register) == 1
        assert self.calls_register[-1].data["domain"] == "test_domain"
        assert self.calls_register[-1].data["service"] == "register_calls"

        assert self.services.call("test_domain", "REGISTER_CALLS", blocking=True)
        self.hass.block_till_done()
        assert len(calls) == 1

    def test_async_service_partial(self):
        """Test registering and calling an wrapped async service."""
        calls = []

        async def service_handler(call):
            """Service handler coroutine."""
            calls.append(call)

        self.services.register(
            "test_domain", "register_calls", functools.partial(service_handler)
        )
        self.hass.block_till_done()

        assert len(self.calls_register) == 1
        assert self.calls_register[-1].data["domain"] == "test_domain"
        assert self.calls_register[-1].data["service"] == "register_calls"

        assert self.services.call("test_domain", "REGISTER_CALLS", blocking=True)
        self.hass.block_till_done()
        assert len(calls) == 1

    def test_callback_service(self):
        """Test registering and calling an async service."""
        calls = []

        @ha.callback
        def service_handler(call):
            """Service handler coroutine."""
            calls.append(call)

        self.services.register("test_domain", "register_calls", service_handler)
        self.hass.block_till_done()

        assert len(self.calls_register) == 1
        assert self.calls_register[-1].data["domain"] == "test_domain"
        assert self.calls_register[-1].data["service"] == "register_calls"

        assert self.services.call("test_domain", "REGISTER_CALLS", blocking=True)
        self.hass.block_till_done()
        assert len(calls) == 1

    def test_remove_service(self):
        """Test remove service."""
        calls_remove = []

        @ha.callback
        def mock_event_remove(event):
            """Mock register event."""
            calls_remove.append(event)

        self.hass.bus.listen(EVENT_SERVICE_REMOVED, mock_event_remove)

        assert self.services.has_service("test_Domain", "test_Service")

        self.services.remove("test_Domain", "test_Service")
        self.hass.block_till_done()

        assert not self.services.has_service("test_Domain", "test_Service")
        assert len(calls_remove) == 1
        assert calls_remove[-1].data["domain"] == "test_domain"
        assert calls_remove[-1].data["service"] == "test_service"

    def test_remove_service_that_not_exists(self):
        """Test remove service that not exists."""
        calls_remove = []

        @ha.callback
        def mock_event_remove(event):
            """Mock register event."""
            calls_remove.append(event)

        self.hass.bus.listen(EVENT_SERVICE_REMOVED, mock_event_remove)

        assert not self.services.has_service("test_xxx", "test_yyy")
        self.services.remove("test_xxx", "test_yyy")
        self.hass.block_till_done()
        assert len(calls_remove) == 0

    def test_async_service_raise_exception(self):
        """Test registering and calling an async service raise exception."""

        async def service_handler(_):
            """Service handler coroutine."""
            raise ValueError

        self.services.register("test_domain", "register_calls", service_handler)
        self.hass.block_till_done()

        with pytest.raises(ValueError):
            assert self.services.call("test_domain", "REGISTER_CALLS", blocking=True)
            self.hass.block_till_done()

        # Non-blocking service call never throw exception
        self.services.call("test_domain", "REGISTER_CALLS", blocking=False)
        self.hass.block_till_done()

    def test_callback_service_raise_exception(self):
        """Test registering and calling an callback service raise exception."""

        @ha.callback
        def service_handler(_):
            """Service handler coroutine."""
            raise ValueError

        self.services.register("test_domain", "register_calls", service_handler)
        self.hass.block_till_done()

        with pytest.raises(ValueError):
            assert self.services.call("test_domain", "REGISTER_CALLS", blocking=True)
            self.hass.block_till_done()

        # Non-blocking service call never throw exception
        self.services.call("test_domain", "REGISTER_CALLS", blocking=False)
        self.hass.block_till_done()


class TestConfig(unittest.TestCase):
    """Test configuration methods."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.config = ha.Config(None)
        assert self.config.config_dir is None

    def test_path_with_file(self):
        """Test get_config_path method."""
        self.config.config_dir = "/test/ha-config"
        assert self.config.path("test.conf") == "/test/ha-config/test.conf"

    def test_path_with_dir_and_file(self):
        """Test get_config_path method."""
        self.config.config_dir = "/test/ha-config"
        assert self.config.path("dir", "test.conf") == "/test/ha-config/dir/test.conf"

    def test_as_dict(self):
        """Test as dict."""
        self.config.config_dir = "/test/ha-config"
        self.config.hass = MagicMock()
        type(self.config.hass.state).value = PropertyMock(return_value="RUNNING")
        expected = {
            "latitude": 0,
            "longitude": 0,
            "elevation": 0,
            CONF_UNIT_SYSTEM: METRIC_SYSTEM.as_dict(),
            "location_name": "Home",
            "time_zone": "UTC",
            "components": set(),
            "config_dir": "/test/ha-config",
            "whitelist_external_dirs": set(),
            "allowlist_external_urls": set(),
            "version": __version__,
            "config_source": "default",
            "safe_mode": False,
            "state": "RUNNING",
            "external_url": None,
            "internal_url": None,
        }

        assert expected == self.config.as_dict()

    def test_is_allowed_path(self):
        """Test is_allowed_path method."""
        with TemporaryDirectory() as tmp_dir:
            # The created dir is in /tmp. This is a symlink on OS X
            # causing this test to fail unless we resolve path first.
            self.config.whitelist_external_dirs = {os.path.realpath(tmp_dir)}

            test_file = os.path.join(tmp_dir, "test.jpg")
            with open(test_file, "w") as tmp_file:
                tmp_file.write("test")

            valid = [test_file, tmp_dir, os.path.join(tmp_dir, "notfound321")]
            for path in valid:
                assert self.config.is_allowed_path(path)

            self.config.whitelist_external_dirs = {"/home", "/var"}

            unvalid = [
                "/hass/config/secure",
                "/etc/passwd",
                "/root/secure_file",
                "/var/../etc/passwd",
                test_file,
            ]
            for path in unvalid:
                assert not self.config.is_allowed_path(path)

            with pytest.raises(AssertionError):
                self.config.is_allowed_path(None)

    def test_is_allowed_external_url(self):
        """Test is_allowed_external_url method."""
        self.config.allowlist_external_urls = [
            "http://x.com/",
            "https://y.com/bla/",
            "https://z.com/images/1.jpg/",
        ]

        valid = [
            "http://x.com/1.jpg",
            "http://x.com",
            "https://y.com/bla/",
            "https://y.com/bla/2.png",
            "https://z.com/images/1.jpg",
        ]
        for url in valid:
            assert self.config.is_allowed_external_url(url)

        invalid = [
            "https://a.co",
            "https://y.com/bla_wrong",
            "https://y.com/bla/../image.jpg",
            "https://z.com/images",
        ]
        for url in invalid:
            assert not self.config.is_allowed_external_url(url)


async def test_event_on_update(hass):
    """Test that event is fired on update."""
    events = []

    @ha.callback
    def callback(event):
        events.append(event)

    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, callback)

    assert hass.config.latitude != 12

    await hass.config.async_update(latitude=12)
    await hass.async_block_till_done()

    assert hass.config.latitude == 12
    assert len(events) == 1
    assert events[0].data == {"latitude": 12}


async def test_bad_timezone_raises_value_error(hass):
    """Test bad timezone raises ValueError."""
    with pytest.raises(ValueError):
        await hass.config.async_update(time_zone="not_a_timezone")


@patch("homeassistant.core.monotonic")
def test_create_timer(mock_monotonic, loop):
    """Test create timer."""
    hass = MagicMock()
    funcs = []
    orig_callback = ha.callback

    def mock_callback(func):
        funcs.append(func)
        return orig_callback(func)

    mock_monotonic.side_effect = 10.2, 10.8, 11.3

    with patch.object(ha, "callback", mock_callback), patch(
        "homeassistant.core.dt_util.utcnow",
        return_value=datetime(2018, 12, 31, 3, 4, 5, 333333),
    ):
        ha._async_create_timer(hass)

    assert len(funcs) == 2
    fire_time_event, stop_timer = funcs

    assert len(hass.loop.call_later.mock_calls) == 1
    delay, callback, target = hass.loop.call_later.mock_calls[0][1]
    assert abs(delay - 0.666667) < 0.001
    assert callback is fire_time_event
    assert abs(target - 10.866667) < 0.001

    with patch(
        "homeassistant.core.dt_util.utcnow",
        return_value=datetime(2018, 12, 31, 3, 4, 6, 100000),
    ):
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


@patch("homeassistant.core.monotonic")
def test_timer_out_of_sync(mock_monotonic, loop):
    """Test create timer."""
    hass = MagicMock()
    funcs = []
    orig_callback = ha.callback

    def mock_callback(func):
        funcs.append(func)
        return orig_callback(func)

    mock_monotonic.side_effect = 10.2, 13.3, 13.4

    with patch.object(ha, "callback", mock_callback), patch(
        "homeassistant.core.dt_util.utcnow",
        return_value=datetime(2018, 12, 31, 3, 4, 5, 333333),
    ):
        ha._async_create_timer(hass)

    delay, callback, target = hass.loop.call_later.mock_calls[0][1]

    with patch(
        "homeassistant.core.dt_util.utcnow",
        return_value=datetime(2018, 12, 31, 3, 4, 8, 200000),
    ):
        callback(target)

        event_type, event_data = hass.bus.async_fire.mock_calls[1][1]
        assert event_type == EVENT_TIMER_OUT_OF_SYNC
        assert abs(event_data[ATTR_SECONDS] - 2.433333) < 0.001

        assert len(funcs) == 2
        fire_time_event, _ = funcs

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
        with patch("homeassistant.core._async_create_timer") as mock_timer:
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
        with patch(
            "homeassistant.core.timeout", side_effect=asyncio.TimeoutError
        ), patch("homeassistant.core._async_create_timer") as mock_timer:
            yield from hass.async_start()

        assert hass.state == ha.CoreState.running
        assert len(mock_timer.mock_calls) == 1
        assert mock_timer.mock_calls[0][1][0] is hass
        assert "Something is blocking Home Assistant" in caplog.text

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
    calls = async_mock_service(hass, "test", "inner")
    context = ha.Context()

    async def handle_outer(call):
        """Handle outer service call."""
        calls.append(call)
        call1 = hass.services.async_call(
            "test", "inner", blocking=True, context=call.context
        )
        call2 = hass.services.async_call(
            "test", "inner", blocking=True, context=call.context
        )
        await asyncio.wait([call1, call2])
        calls.append(call)

    hass.services.async_register("test", "outer", handle_outer)

    await hass.services.async_call("test", "outer", blocking=True, context=context)

    assert len(calls) == 4
    assert [call.service for call in calls] == ["outer", "inner", "inner", "outer"]
    assert all(call.context is context for call in calls)


async def test_service_call_event_contains_original_data(hass):
    """Test that service call event contains original data."""
    events = []

    @ha.callback
    def callback(event):
        events.append(event)

    hass.bus.async_listen(EVENT_CALL_SERVICE, callback)

    calls = async_mock_service(
        hass, "test", "service", vol.Schema({"number": vol.Coerce(int)})
    )

    context = ha.Context()
    await hass.services.async_call(
        "test", "service", {"number": "23"}, blocking=True, context=context
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["service_data"]["number"] == "23"
    assert events[0].context is context
    assert len(calls) == 1
    assert calls[0].data["number"] == 23
    assert calls[0].context is context


def test_context():
    """Test context init."""
    c = ha.Context()
    assert c.user_id is None
    assert c.parent_id is None
    assert c.id is not None

    c = ha.Context(23, 100)
    assert c.user_id == 23
    assert c.parent_id == 100
    assert c.id is not None


async def test_async_functions_with_callback(hass):
    """Test we deal with async functions accidentally marked as callback."""
    runs = []

    @ha.callback
    async def test():
        runs.append(True)

    await hass.async_add_job(test)
    assert len(runs) == 1

    hass.async_run_job(test)
    await hass.async_block_till_done()
    assert len(runs) == 2

    @ha.callback
    async def service_handler(call):
        runs.append(True)

    hass.services.async_register("test_domain", "test_service", service_handler)

    await hass.services.async_call("test_domain", "test_service", blocking=True)
    assert len(runs) == 3


@pytest.mark.parametrize("cancel_call", [True, False])
async def test_cancel_service_task(hass, cancel_call):
    """Test cancellation."""
    service_called = asyncio.Event()
    service_cancelled = False

    async def service_handler(call):
        nonlocal service_cancelled
        service_called.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            service_cancelled = True
            raise

    hass.services.async_register("test_domain", "test_service", service_handler)
    call_task = hass.async_create_task(
        hass.services.async_call("test_domain", "test_service", blocking=True)
    )

    tasks_1 = asyncio.all_tasks()
    await asyncio.wait_for(service_called.wait(), timeout=1)
    tasks_2 = asyncio.all_tasks() - tasks_1
    assert len(tasks_2) == 1
    service_task = tasks_2.pop()

    if cancel_call:
        call_task.cancel()
    else:
        service_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await call_task

    assert service_cancelled


def test_valid_entity_id():
    """Test valid entity ID."""
    for invalid in [
        "_light.kitchen",
        ".kitchen",
        ".light.kitchen",
        "light_.kitchen",
        "light._kitchen",
        "light.",
        "light.kitchen__ceiling",
        "light.kitchen_yo_",
        "light.kitchen.",
        "Light.kitchen",
        "light.Kitchen",
        "lightkitchen",
    ]:
        assert not ha.valid_entity_id(invalid), invalid

    for valid in [
        "1.a",
        "1light.kitchen",
        "a.1",
        "a.a",
        "input_boolean.hello_world_0123",
        "light.1kitchen",
        "light.kitchen",
        "light.something_yoo",
    ]:
        assert ha.valid_entity_id(valid), valid


async def test_migration_base_url(hass, hass_storage):
    """Test that we migrate base url to internal/external url."""
    config = ha.Config(hass)
    stored = {"version": 1, "data": {}}
    hass_storage[ha.CORE_STORAGE_KEY] = stored
    with patch.object(hass.bus, "async_listen_once") as mock_listen:
        # Empty config
        await config.async_load()
        assert len(mock_listen.mock_calls) == 0

        # With just a name
        stored["data"] = {"location_name": "Test Name"}
        await config.async_load()
        assert len(mock_listen.mock_calls) == 1

        # With external url
        stored["data"]["external_url"] = "https://example.com"
        await config.async_load()
        assert len(mock_listen.mock_calls) == 1

    # Test that the event listener works
    assert mock_listen.mock_calls[0][1][0] == EVENT_HOMEASSISTANT_START

    # External
    hass.config.api = Mock(deprecated_base_url="https://loaded-example.com")
    await mock_listen.mock_calls[0][1][1](None)
    assert config.external_url == "https://loaded-example.com"

    # Internal
    for internal in ("http://hass.local", "http://192.168.1.100:8123"):
        hass.config.api = Mock(deprecated_base_url=internal)
        await mock_listen.mock_calls[0][1][1](None)
        assert config.internal_url == internal


async def test_additional_data_in_core_config(hass, hass_storage):
    """Test that we can handle additional data in core configuration."""
    config = ha.Config(hass)
    hass_storage[ha.CORE_STORAGE_KEY] = {
        "version": 1,
        "data": {"location_name": "Test Name", "additional_valid_key": "value"},
    }
    await config.async_load()
    assert config.location_name == "Test Name"


async def test_start_events(hass):
    """Test events fired when starting Home Assistant."""
    hass.state = ha.CoreState.not_running

    all_events = []

    @ha.callback
    def capture_events(ev):
        all_events.append(ev.event_type)

    hass.bus.async_listen(MATCH_ALL, capture_events)

    core_states = []

    @ha.callback
    def capture_core_state(_):
        core_states.append(hass.state)

    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, capture_core_state)

    await hass.async_start()
    await hass.async_block_till_done()

    assert all_events == [
        EVENT_CORE_CONFIG_UPDATE,
        EVENT_HOMEASSISTANT_START,
        EVENT_CORE_CONFIG_UPDATE,
        EVENT_HOMEASSISTANT_STARTED,
    ]
    assert core_states == [ha.CoreState.starting, ha.CoreState.running]
