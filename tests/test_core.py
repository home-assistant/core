"""Test to verify that Home Assistant core works."""
from __future__ import annotations

import array
import asyncio
from datetime import datetime, timedelta
import functools
import gc
import logging
import os
from tempfile import TemporaryDirectory
import threading
import time
from typing import Any
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import async_timeout
import pytest
import voluptuous as vol

from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
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
    MATCH_ALL,
    __version__,
)
import homeassistant.core as ha
from homeassistant.core import (
    HassJob,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    State,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import (
    HomeAssistantError,
    InvalidEntityFormatError,
    InvalidStateError,
    MaxLengthExceeded,
    ServiceNotFound,
)
import homeassistant.util.dt as dt_util
from homeassistant.util.read_only_dict import ReadOnlyDict
from homeassistant.util.unit_system import METRIC_SYSTEM

from .common import async_capture_events, async_mock_service

PST = dt_util.get_time_zone("America/Los_Angeles")


def test_split_entity_id() -> None:
    """Test split_entity_id."""
    assert ha.split_entity_id("domain.object_id") == ("domain", "object_id")
    with pytest.raises(ValueError):
        ha.split_entity_id("")
    with pytest.raises(ValueError):
        ha.split_entity_id(".")
    with pytest.raises(ValueError):
        ha.split_entity_id("just_domain")
    with pytest.raises(ValueError):
        ha.split_entity_id("empty_object_id.")
    with pytest.raises(ValueError):
        ha.split_entity_id(".empty_domain")


def test_async_add_hass_job_schedule_callback() -> None:
    """Test that we schedule callbacks and add jobs to the job pool."""
    hass = MagicMock()
    job = MagicMock()

    ha.HomeAssistant.async_add_hass_job(hass, ha.HassJob(ha.callback(job)))
    assert len(hass.loop.call_soon.mock_calls) == 1
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.add_job.mock_calls) == 0


def test_async_add_hass_job_coro_named(hass: HomeAssistant) -> None:
    """Test that we schedule coroutines and add jobs to the job pool with a name."""

    async def mycoro():
        pass

    job = ha.HassJob(mycoro, "named coro")
    assert "named coro" in str(job)
    assert job.name == "named coro"
    task = ha.HomeAssistant.async_add_hass_job(hass, job)
    assert "named coro" in str(task)


def test_async_add_hass_job_schedule_partial_callback() -> None:
    """Test that we schedule partial coros and add jobs to the job pool."""
    hass = MagicMock()
    job = MagicMock()
    partial = functools.partial(ha.callback(job))

    ha.HomeAssistant.async_add_hass_job(hass, ha.HassJob(partial))
    assert len(hass.loop.call_soon.mock_calls) == 1
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.add_job.mock_calls) == 0


def test_async_add_hass_job_schedule_coroutinefunction(event_loop) -> None:
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=event_loop))

    async def job():
        pass

    ha.HomeAssistant.async_add_hass_job(hass, ha.HassJob(job))
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0


def test_async_add_hass_job_schedule_partial_coroutinefunction(event_loop) -> None:
    """Test that we schedule partial coros and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=event_loop))

    async def job():
        pass

    partial = functools.partial(job)

    ha.HomeAssistant.async_add_hass_job(hass, ha.HassJob(partial))
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0


def test_async_add_job_add_hass_threaded_job_to_pool() -> None:
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock()

    def job():
        pass

    ha.HomeAssistant.async_add_hass_job(hass, ha.HassJob(job))
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.loop.run_in_executor.mock_calls) == 2


def test_async_create_task_schedule_coroutine(event_loop) -> None:
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=event_loop))

    async def job():
        pass

    ha.HomeAssistant.async_create_task(hass, job())
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0


def test_async_create_task_schedule_coroutine_with_name(event_loop) -> None:
    """Test that we schedule coroutines and add jobs to the job pool with a name."""
    hass = MagicMock(loop=MagicMock(wraps=event_loop))

    async def job():
        pass

    task = ha.HomeAssistant.async_create_task(hass, job(), "named task")
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0
    assert "named task" in str(task)


def test_async_run_hass_job_calls_callback() -> None:
    """Test that the callback annotation is respected."""
    hass = MagicMock()
    calls = []

    def job():
        calls.append(1)

    ha.HomeAssistant.async_run_hass_job(hass, ha.HassJob(ha.callback(job)))
    assert len(calls) == 1
    assert len(hass.async_add_job.mock_calls) == 0


def test_async_run_hass_job_delegates_non_async() -> None:
    """Test that the callback annotation is respected."""
    hass = MagicMock()
    calls = []

    def job():
        calls.append(1)

    ha.HomeAssistant.async_run_hass_job(hass, ha.HassJob(job))
    assert len(calls) == 0
    assert len(hass.async_add_hass_job.mock_calls) == 1


async def test_async_get_hass_can_be_called(hass: HomeAssistant) -> None:
    """Test calling async_get_hass via different paths.

    The test asserts async_get_hass can be called from:
    - Coroutines and callbacks
    - Callbacks scheduled from callbacks, coroutines and threads
    - Coroutines scheduled from callbacks, coroutines and threads

    The test also asserts async_get_hass can not be called from threads
    other than the event loop.
    """
    task_finished = asyncio.Event()

    def can_call_async_get_hass() -> bool:
        """Test if it's possible to call async_get_hass."""
        try:
            if ha.async_get_hass() is hass:
                return True
            raise Exception
        except HomeAssistantError:
            return False

        raise Exception

    # Test scheduling a coroutine which calls async_get_hass via hass.async_create_task
    async def _async_create_task() -> None:
        task_finished.set()
        assert can_call_async_get_hass()

    hass.async_create_task(_async_create_task(), "create_task")
    async with async_timeout.timeout(1):
        await task_finished.wait()
    task_finished.clear()

    # Test scheduling a callback which calls async_get_hass via hass.async_add_job
    @callback
    def _add_job() -> None:
        assert can_call_async_get_hass()
        task_finished.set()

    hass.async_add_job(_add_job)
    async with async_timeout.timeout(1):
        await task_finished.wait()
    task_finished.clear()

    # Test scheduling a callback which calls async_get_hass from a callback
    @callback
    def _schedule_callback_from_callback() -> None:
        @callback
        def _callback():
            assert can_call_async_get_hass()
            task_finished.set()

        # Test the scheduled callback itself can call async_get_hass
        assert can_call_async_get_hass()
        hass.async_add_job(_callback)

    _schedule_callback_from_callback()
    async with async_timeout.timeout(1):
        await task_finished.wait()
    task_finished.clear()

    # Test scheduling a coroutine which calls async_get_hass from a callback
    @callback
    def _schedule_coroutine_from_callback() -> None:
        async def _coroutine():
            assert can_call_async_get_hass()
            task_finished.set()

        # Test the scheduled callback itself can call async_get_hass
        assert can_call_async_get_hass()
        hass.async_add_job(_coroutine())

    _schedule_coroutine_from_callback()
    async with async_timeout.timeout(1):
        await task_finished.wait()
    task_finished.clear()

    # Test scheduling a callback which calls async_get_hass from a coroutine
    async def _schedule_callback_from_coroutine() -> None:
        @callback
        def _callback():
            assert can_call_async_get_hass()
            task_finished.set()

        # Test the coroutine itself can call async_get_hass
        assert can_call_async_get_hass()
        hass.async_add_job(_callback)

    await _schedule_callback_from_coroutine()
    async with async_timeout.timeout(1):
        await task_finished.wait()
    task_finished.clear()

    # Test scheduling a coroutine which calls async_get_hass from a coroutine
    async def _schedule_callback_from_coroutine() -> None:
        async def _coroutine():
            assert can_call_async_get_hass()
            task_finished.set()

        # Test the coroutine itself can call async_get_hass
        assert can_call_async_get_hass()
        await hass.async_create_task(_coroutine())

    await _schedule_callback_from_coroutine()
    async with async_timeout.timeout(1):
        await task_finished.wait()
    task_finished.clear()

    # Test scheduling a callback which calls async_get_hass from an executor
    def _async_add_executor_job_add_job() -> None:
        @callback
        def _async_add_job():
            assert can_call_async_get_hass()
            task_finished.set()

        # Test the executor itself can not call async_get_hass
        assert not can_call_async_get_hass()
        hass.add_job(_async_add_job)

    await hass.async_add_executor_job(_async_add_executor_job_add_job)
    async with async_timeout.timeout(1):
        await task_finished.wait()
    task_finished.clear()

    # Test scheduling a coroutine which calls async_get_hass from an executor
    def _async_add_executor_job_create_task() -> None:
        async def _async_create_task() -> None:
            assert can_call_async_get_hass()
            task_finished.set()

        # Test the executor itself can not call async_get_hass
        assert not can_call_async_get_hass()
        hass.create_task(_async_create_task())

    await hass.async_add_executor_job(_async_add_executor_job_create_task)
    async with async_timeout.timeout(1):
        await task_finished.wait()
    task_finished.clear()

    # Test scheduling a callback which calls async_get_hass from a worker thread
    class MyJobAddJob(threading.Thread):
        @callback
        def _my_threaded_job_add_job(self) -> None:
            assert can_call_async_get_hass()
            task_finished.set()

        def run(self) -> None:
            # Test the worker thread itself can not call async_get_hass
            assert not can_call_async_get_hass()
            hass.add_job(self._my_threaded_job_add_job)

    my_job_add_job = MyJobAddJob()
    my_job_add_job.start()
    async with async_timeout.timeout(1):
        await task_finished.wait()
    task_finished.clear()
    my_job_add_job.join()

    # Test scheduling a coroutine which calls async_get_hass from a worker thread
    class MyJobCreateTask(threading.Thread):
        async def _my_threaded_job_create_task(self) -> None:
            assert can_call_async_get_hass()
            task_finished.set()

        def run(self) -> None:
            # Test the worker thread itself can not call async_get_hass
            assert not can_call_async_get_hass()
            hass.create_task(self._my_threaded_job_create_task())

    my_job_create_task = MyJobCreateTask()
    my_job_create_task.start()
    async with async_timeout.timeout(1):
        await task_finished.wait()
    task_finished.clear()
    my_job_create_task.join()


async def test_stage_shutdown(hass: HomeAssistant) -> None:
    """Simulate a shutdown, test calling stuff."""
    test_stop = async_capture_events(hass, EVENT_HOMEASSISTANT_STOP)
    test_final_write = async_capture_events(hass, EVENT_HOMEASSISTANT_FINAL_WRITE)
    test_close = async_capture_events(hass, EVENT_HOMEASSISTANT_CLOSE)
    test_all = async_capture_events(hass, MATCH_ALL)

    await hass.async_stop()

    assert len(test_stop) == 1
    assert len(test_close) == 1
    assert len(test_final_write) == 1
    assert len(test_all) == 2


async def test_stage_shutdown_with_exit_code(hass: HomeAssistant) -> None:
    """Simulate a shutdown, test calling stuff with exit code checks."""
    test_stop = async_capture_events(hass, EVENT_HOMEASSISTANT_STOP)
    test_final_write = async_capture_events(hass, EVENT_HOMEASSISTANT_FINAL_WRITE)
    test_close = async_capture_events(hass, EVENT_HOMEASSISTANT_CLOSE)
    test_all = async_capture_events(hass, MATCH_ALL)

    event_call_counters = [0, 0, 0]
    expected_exit_code = 101

    async def async_on_stop(event) -> None:
        if hass.exit_code == expected_exit_code:
            event_call_counters[0] += 1

    async def async_on_final_write(event) -> None:
        if hass.exit_code == expected_exit_code:
            event_call_counters[1] += 1

    async def async_on_close(event) -> None:
        if hass.exit_code == expected_exit_code:
            event_call_counters[2] += 1

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_on_stop)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_FINAL_WRITE, async_on_final_write)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, async_on_close)

    await hass.async_stop(expected_exit_code)

    assert len(test_stop) == 1
    assert len(test_close) == 1
    assert len(test_final_write) == 1
    assert len(test_all) == 2

    assert (
        event_call_counters[0] == 1
        and event_call_counters[1] == 1
        and event_call_counters[2] == 1
    )


async def test_shutdown_calls_block_till_done_after_shutdown_run_callback_threadsafe(
    hass: HomeAssistant,
) -> None:
    """Ensure shutdown_run_callback_threadsafe is called before the final async_block_till_done."""
    stop_calls = []

    async def _record_block_till_done():
        nonlocal stop_calls
        stop_calls.append("async_block_till_done")

    def _record_shutdown_run_callback_threadsafe(loop):
        nonlocal stop_calls
        stop_calls.append(("shutdown_run_callback_threadsafe", loop))

    with patch.object(hass, "async_block_till_done", _record_block_till_done), patch(
        "homeassistant.core.shutdown_run_callback_threadsafe",
        _record_shutdown_run_callback_threadsafe,
    ):
        await hass.async_stop()

    assert stop_calls[-2] == ("shutdown_run_callback_threadsafe", hass.loop)
    assert stop_calls[-1] == "async_block_till_done"


async def test_pending_scheduler(hass: HomeAssistant) -> None:
    """Add a coro to pending tasks."""
    call_count = []

    async def test_coro():
        """Test Coro."""
        call_count.append("call")

    for _ in range(3):
        hass.async_add_job(test_coro())

    await asyncio.wait(hass._tasks)

    assert len(hass._tasks) == 0
    assert len(call_count) == 3


async def test_async_add_job_pending_tasks_coro(hass: HomeAssistant) -> None:
    """Add a coro to pending tasks."""
    call_count = []

    async def test_coro():
        """Test Coro."""
        call_count.append("call")

    for _ in range(2):
        hass.add_job(test_coro())

    async def wait_finish_callback():
        """Wait until all stuff is scheduled."""
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    await wait_finish_callback()

    assert len(hass._tasks) == 2
    await hass.async_block_till_done()
    assert len(call_count) == 2


async def test_async_create_task_pending_tasks_coro(hass: HomeAssistant) -> None:
    """Add a coro to pending tasks."""
    call_count = []

    async def test_coro():
        """Test Coro."""
        call_count.append("call")

    for _ in range(2):
        hass.create_task(test_coro())

    async def wait_finish_callback():
        """Wait until all stuff is scheduled."""
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    await wait_finish_callback()

    assert len(hass._tasks) == 2
    await hass.async_block_till_done()
    assert len(call_count) == 2


async def test_async_add_job_pending_tasks_executor(hass: HomeAssistant) -> None:
    """Run an executor in pending tasks."""
    call_count = []

    def test_executor():
        """Test executor."""
        call_count.append("call")

    async def wait_finish_callback():
        """Wait until all stuff is scheduled."""
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    for _ in range(2):
        hass.async_add_job(test_executor)

    await wait_finish_callback()

    await hass.async_block_till_done()
    assert len(call_count) == 2


async def test_async_add_job_pending_tasks_callback(hass: HomeAssistant) -> None:
    """Run a callback in pending tasks."""
    call_count = []

    @ha.callback
    def test_callback():
        """Test callback."""
        call_count.append("call")

    async def wait_finish_callback():
        """Wait until all stuff is scheduled."""
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    for _ in range(2):
        hass.async_add_job(test_callback)

    await wait_finish_callback()

    await hass.async_block_till_done()

    assert len(hass._tasks) == 0
    assert len(call_count) == 2


async def test_add_job_with_none(hass: HomeAssistant) -> None:
    """Try to add a job with None as function."""
    with pytest.raises(ValueError):
        hass.async_add_job(None, "test_arg")


def test_event_eq() -> None:
    """Test events."""
    now = dt_util.utcnow()
    data = {"some": "attr"}
    context = ha.Context()
    event1, event2 = (
        ha.Event("some_type", data, time_fired=now, context=context) for _ in range(2)
    )

    assert event1.as_dict() == event2.as_dict()


def test_event_repr() -> None:
    """Test that Event repr method works."""
    assert str(ha.Event("TestEvent")) == "<Event TestEvent[L]>"

    assert (
        str(ha.Event("TestEvent", {"beer": "nice"}, ha.EventOrigin.remote))
        == "<Event TestEvent[R]: beer=nice>"
    )


def test_event_as_dict() -> None:
    """Test an Event as dictionary."""
    event_type = "some_type"
    now = dt_util.utcnow()
    data = {"some": "attr"}

    event = ha.Event(event_type, data, ha.EventOrigin.local, now)
    expected = {
        "event_type": event_type,
        "data": data,
        "origin": "LOCAL",
        "time_fired": now.isoformat(),
        "context": {
            "id": event.context.id,
            "parent_id": None,
            "user_id": event.context.user_id,
        },
    }
    assert event.as_dict() == expected
    # 2nd time to verify cache
    assert event.as_dict() == expected


def test_state_as_dict() -> None:
    """Test a State as dictionary."""
    last_time = datetime(1984, 12, 8, 12, 0, 0)
    state = ha.State(
        "happy.happy",
        "on",
        {"pig": "dog"},
        last_updated=last_time,
        last_changed=last_time,
    )
    expected = {
        "context": {
            "id": state.context.id,
            "parent_id": None,
            "user_id": state.context.user_id,
        },
        "entity_id": "happy.happy",
        "attributes": {"pig": "dog"},
        "last_changed": last_time.isoformat(),
        "last_updated": last_time.isoformat(),
        "state": "on",
    }
    as_dict_1 = state.as_dict()
    assert isinstance(as_dict_1, ReadOnlyDict)
    assert isinstance(as_dict_1["attributes"], ReadOnlyDict)
    assert isinstance(as_dict_1["context"], ReadOnlyDict)
    assert as_dict_1 == expected
    # 2nd time to verify cache
    assert state.as_dict() == expected
    assert state.as_dict() is as_dict_1


def test_state_as_dict_json() -> None:
    """Test a State as JSON."""
    last_time = datetime(1984, 12, 8, 12, 0, 0)
    state = ha.State(
        "happy.happy",
        "on",
        {"pig": "dog"},
        last_updated=last_time,
        last_changed=last_time,
        context=ha.Context(id="01H0D6K3RFJAYAV2093ZW30PCW"),
    )
    expected = (
        '{"entity_id":"happy.happy","state":"on","attributes":{"pig":"dog"},'
        '"last_changed":"1984-12-08T12:00:00","last_updated":"1984-12-08T12:00:00",'
        '"context":{"id":"01H0D6K3RFJAYAV2093ZW30PCW","parent_id":null,"user_id":null}}'
    )
    as_dict_json_1 = state.as_dict_json()
    assert as_dict_json_1 == expected
    # 2nd time to verify cache
    assert state.as_dict_json() == expected
    assert state.as_dict_json() is as_dict_json_1


def test_state_as_compressed_state() -> None:
    """Test a State as compressed state."""
    last_time = datetime(1984, 12, 8, 12, 0, 0, tzinfo=dt_util.UTC)
    state = ha.State(
        "happy.happy",
        "on",
        {"pig": "dog"},
        last_updated=last_time,
        last_changed=last_time,
    )
    expected = {
        "a": {"pig": "dog"},
        "c": state.context.id,
        "lc": last_time.timestamp(),
        "s": "on",
    }
    as_compressed_state = state.as_compressed_state()
    # We are not too concerned about these being ReadOnlyDict
    # since we don't expect them to be called by external callers
    assert as_compressed_state == expected
    # 2nd time to verify cache
    assert state.as_compressed_state() == expected


def test_state_as_compressed_state_unique_last_updated() -> None:
    """Test a State as compressed state where last_changed is not last_updated."""
    last_changed = datetime(1984, 12, 8, 11, 0, 0, tzinfo=dt_util.UTC)
    last_updated = datetime(1984, 12, 8, 12, 0, 0, tzinfo=dt_util.UTC)
    state = ha.State(
        "happy.happy",
        "on",
        {"pig": "dog"},
        last_updated=last_updated,
        last_changed=last_changed,
    )
    expected = {
        "a": {"pig": "dog"},
        "c": state.context.id,
        "lc": last_changed.timestamp(),
        "lu": last_updated.timestamp(),
        "s": "on",
    }
    as_compressed_state = state.as_compressed_state()
    # We are not too concerned about these being ReadOnlyDict
    # since we don't expect them to be called by external callers
    assert as_compressed_state == expected
    # 2nd time to verify cache
    assert state.as_compressed_state() == expected


def test_state_as_compressed_state_json() -> None:
    """Test a State as a JSON compressed state."""
    last_time = datetime(1984, 12, 8, 12, 0, 0, tzinfo=dt_util.UTC)
    state = ha.State(
        "happy.happy",
        "on",
        {"pig": "dog"},
        last_updated=last_time,
        last_changed=last_time,
        context=ha.Context(id="01H0D6H5K3SZJ3XGDHED1TJ79N"),
    )
    expected = '"happy.happy":{"s":"on","a":{"pig":"dog"},"c":"01H0D6H5K3SZJ3XGDHED1TJ79N","lc":471355200.0}'
    as_compressed_state = state.as_compressed_state_json()
    # We are not too concerned about these being ReadOnlyDict
    # since we don't expect them to be called by external callers
    assert as_compressed_state == expected
    # 2nd time to verify cache
    assert state.as_compressed_state_json() == expected
    assert state.as_compressed_state_json() is as_compressed_state


async def test_eventbus_add_remove_listener(hass: HomeAssistant) -> None:
    """Test remove_listener method."""
    old_count = len(hass.bus.async_listeners())

    def listener(_):
        pass

    unsub = hass.bus.async_listen("test", listener)

    assert old_count + 1 == len(hass.bus.async_listeners())

    # Remove listener
    unsub()
    assert old_count == len(hass.bus.async_listeners())

    # Should do nothing now
    unsub()


async def test_eventbus_filtered_listener(hass: HomeAssistant) -> None:
    """Test we can prefilter events."""
    calls = []

    @ha.callback
    def listener(event):
        """Mock listener."""
        calls.append(event)

    @ha.callback
    def filter(event):
        """Mock filter."""
        return not event.data["filtered"]

    unsub = hass.bus.async_listen("test", listener, event_filter=filter)

    hass.bus.async_fire("test", {"filtered": True})
    await hass.async_block_till_done()

    assert len(calls) == 0

    hass.bus.async_fire("test", {"filtered": False})
    await hass.async_block_till_done()

    assert len(calls) == 1

    unsub()


async def test_eventbus_run_immediately(hass: HomeAssistant) -> None:
    """Test we can call events immediately."""
    calls = []

    @ha.callback
    def listener(event):
        """Mock listener."""
        calls.append(event)

    unsub = hass.bus.async_listen("test", listener, run_immediately=True)

    hass.bus.async_fire("test", {"event": True})
    # No async_block_till_done here
    assert len(calls) == 1

    unsub()


async def test_eventbus_unsubscribe_listener(hass: HomeAssistant) -> None:
    """Test unsubscribe listener from returned function."""
    calls = []

    @ha.callback
    def listener(event):
        """Mock listener."""
        calls.append(event)

    unsub = hass.bus.async_listen("test", listener)

    hass.bus.async_fire("test")
    await hass.async_block_till_done()

    assert len(calls) == 1

    unsub()

    hass.bus.async_fire("event")
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_eventbus_listen_once_event_with_callback(hass: HomeAssistant) -> None:
    """Test listen_once_event method."""
    runs = []

    @ha.callback
    def event_handler(event):
        runs.append(event)

    hass.bus.async_listen_once("test_event", event_handler)

    hass.bus.async_fire("test_event")
    # Second time it should not increase runs
    hass.bus.async_fire("test_event")

    await hass.async_block_till_done()
    assert len(runs) == 1


async def test_eventbus_listen_once_event_with_coroutine(hass: HomeAssistant) -> None:
    """Test listen_once_event method."""
    runs = []

    async def event_handler(event):
        runs.append(event)

    hass.bus.async_listen_once("test_event", event_handler)

    hass.bus.async_fire("test_event")
    # Second time it should not increase runs
    hass.bus.async_fire("test_event")

    await hass.async_block_till_done()
    assert len(runs) == 1


async def test_eventbus_listen_once_event_with_thread(hass: HomeAssistant) -> None:
    """Test listen_once_event method."""
    runs = []

    def event_handler(event):
        runs.append(event)

    hass.bus.async_listen_once("test_event", event_handler)

    hass.bus.async_fire("test_event")
    # Second time it should not increase runs
    hass.bus.async_fire("test_event")

    await hass.async_block_till_done()
    assert len(runs) == 1


async def test_eventbus_thread_event_listener(hass: HomeAssistant) -> None:
    """Test thread event listener."""
    thread_calls = []

    def thread_listener(event):
        thread_calls.append(event)

    hass.bus.async_listen("test_thread", thread_listener)
    hass.bus.async_fire("test_thread")
    await hass.async_block_till_done()
    assert len(thread_calls) == 1


async def test_eventbus_callback_event_listener(hass: HomeAssistant) -> None:
    """Test callback event listener."""
    callback_calls = []

    @ha.callback
    def callback_listener(event):
        callback_calls.append(event)

    hass.bus.async_listen("test_callback", callback_listener)
    hass.bus.async_fire("test_callback")
    await hass.async_block_till_done()
    assert len(callback_calls) == 1


async def test_eventbus_coroutine_event_listener(hass: HomeAssistant) -> None:
    """Test coroutine event listener."""
    coroutine_calls = []

    async def coroutine_listener(event):
        coroutine_calls.append(event)

    hass.bus.async_listen("test_coroutine", coroutine_listener)
    hass.bus.async_fire("test_coroutine")
    await hass.async_block_till_done()
    assert len(coroutine_calls) == 1


async def test_eventbus_max_length_exceeded(hass: HomeAssistant) -> None:
    """Test that an exception is raised when the max character length is exceeded."""

    long_evt_name = (
        "this_event_exceeds_the_max_character_length_even_with_the_new_limit"
    )

    with pytest.raises(MaxLengthExceeded) as exc_info:
        hass.bus.async_fire(long_evt_name)

    assert exc_info.value.property_name == "event_type"
    assert exc_info.value.max_length == 64
    assert exc_info.value.value == long_evt_name


def test_state_init() -> None:
    """Test state.init."""
    with pytest.raises(InvalidEntityFormatError):
        ha.State("invalid_entity_format", "test_state")

    with pytest.raises(InvalidStateError):
        ha.State("domain.long_state", "t" * 256)


def test_state_domain() -> None:
    """Test domain."""
    state = ha.State("some_domain.hello", "world")
    assert state.domain == "some_domain"


def test_state_object_id() -> None:
    """Test object ID."""
    state = ha.State("domain.hello", "world")
    assert state.object_id == "hello"


def test_state_name_if_no_friendly_name_attr() -> None:
    """Test if there is no friendly name."""
    state = ha.State("domain.hello_world", "world")
    assert state.name == "hello world"


def test_state_name_if_friendly_name_attr() -> None:
    """Test if there is a friendly name."""
    name = "Some Unique Name"
    state = ha.State("domain.hello_world", "world", {ATTR_FRIENDLY_NAME: name})
    assert state.name == name


def test_state_dict_conversion() -> None:
    """Test conversion of dict."""
    state = ha.State("domain.hello", "world", {"some": "attr"})
    assert state.as_dict() == ha.State.from_dict(state.as_dict()).as_dict()


def test_state_dict_conversion_with_wrong_data() -> None:
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


def test_state_repr() -> None:
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
        == "<state happy.happy=on; brightness=144 @ 1984-12-08T12:00:00+00:00>"
    )


async def test_statemachine_is_state(hass: HomeAssistant) -> None:
    """Test is_state method."""
    hass.states.async_set("light.bowl", "on", {})
    assert hass.states.is_state("light.Bowl", "on")
    assert not hass.states.is_state("light.Bowl", "off")
    assert not hass.states.is_state("light.Non_existing", "on")


async def test_statemachine_entity_ids(hass: HomeAssistant) -> None:
    """Test get_entity_ids method."""
    hass.states.async_set("light.bowl", "on", {})
    hass.states.async_set("SWITCH.AC", "off", {})
    ent_ids = hass.states.async_entity_ids()
    assert len(ent_ids) == 2
    assert "light.bowl" in ent_ids
    assert "switch.ac" in ent_ids

    ent_ids = hass.states.async_entity_ids("light")
    assert len(ent_ids) == 1
    assert "light.bowl" in ent_ids

    states = sorted(state.entity_id for state in hass.states.async_all())
    assert states == ["light.bowl", "switch.ac"]


async def test_statemachine_remove(hass: HomeAssistant) -> None:
    """Test remove method."""
    hass.states.async_set("light.bowl", "on", {})
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    assert "light.bowl" in hass.states.async_entity_ids()
    assert hass.states.async_remove("light.bowl")
    await hass.async_block_till_done()

    assert "light.bowl" not in hass.states.async_entity_ids()
    assert len(events) == 1
    assert events[0].data.get("entity_id") == "light.bowl"
    assert events[0].data.get("old_state") is not None
    assert events[0].data["old_state"].entity_id == "light.bowl"
    assert events[0].data.get("new_state") is None

    # If it does not exist, we should get False
    assert not hass.states.async_remove("light.Bowl")
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_statemachine_case_insensitivty(hass: HomeAssistant) -> None:
    """Test insensitivty."""
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    hass.states.async_set("light.BOWL", "off")
    await hass.async_block_till_done()

    assert hass.states.is_state("light.bowl", "off")
    assert len(events) == 1


async def test_statemachine_last_changed_not_updated_on_same_state(
    hass: HomeAssistant,
) -> None:
    """Test to not update the existing, same state."""
    hass.states.async_set("light.bowl", "on", {})
    state = hass.states.get("light.Bowl")

    future = dt_util.utcnow() + timedelta(hours=10)

    with patch("homeassistant.util.dt.utcnow", return_value=future):
        hass.states.async_set("light.Bowl", "on", {"attr": "triggers_change"})
        await hass.async_block_till_done()

    state2 = hass.states.get("light.Bowl")
    assert state2 is not None
    assert state.last_changed == state2.last_changed


async def test_statemachine_force_update(hass: HomeAssistant) -> None:
    """Test force update option."""
    hass.states.async_set("light.bowl", "on", {})
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    hass.states.async_set("light.bowl", "on")
    await hass.async_block_till_done()
    assert len(events) == 0

    hass.states.async_set("light.bowl", "on", None, True)
    await hass.async_block_till_done()
    assert len(events) == 1


def test_service_call_repr() -> None:
    """Test ServiceCall repr."""
    call = ha.ServiceCall("homeassistant", "start")
    assert str(call) == f"<ServiceCall homeassistant.start (c:{call.context.id})>"

    call2 = ha.ServiceCall("homeassistant", "start", {"fast": "yes"})
    assert (
        str(call2)
        == f"<ServiceCall homeassistant.start (c:{call2.context.id}): fast=yes>"
    )


async def test_serviceregistry_has_service(hass: HomeAssistant) -> None:
    """Test has_service method."""
    hass.services.async_register("test_domain", "test_service", lambda call: None)
    assert len(hass.services.async_services()) == 1
    assert hass.services.has_service("tesT_domaiN", "tesT_servicE")
    assert not hass.services.has_service("test_domain", "non_existing")
    assert not hass.services.has_service("non_existing", "test_service")


async def test_serviceregistry_call_with_blocking_done_in_time(
    hass: HomeAssistant,
) -> None:
    """Test call with blocking."""
    registered_events = async_capture_events(hass, EVENT_SERVICE_REGISTERED)
    calls = async_mock_service(hass, "test_domain", "register_calls")
    await hass.async_block_till_done()

    assert len(registered_events) == 1
    assert registered_events[0].data["domain"] == "test_domain"
    assert registered_events[0].data["service"] == "register_calls"

    await hass.services.async_call("test_domain", "REGISTER_CALLS", blocking=True)
    assert len(calls) == 1


async def test_serviceregistry_call_non_existing_with_blocking(
    hass: HomeAssistant,
) -> None:
    """Test non-existing with blocking."""
    with pytest.raises(ha.ServiceNotFound):
        await hass.services.async_call("test_domain", "i_do_not_exist", blocking=True)


async def test_serviceregistry_async_service(hass: HomeAssistant) -> None:
    """Test registering and calling an async service."""
    calls = []

    async def service_handler(call):
        """Service handler coroutine."""
        calls.append(call)

    hass.services.async_register("test_domain", "register_calls", service_handler)

    await hass.services.async_call("test_domain", "REGISTER_CALLS", blocking=True)
    assert len(calls) == 1


async def test_serviceregistry_async_service_partial(hass: HomeAssistant) -> None:
    """Test registering and calling an wrapped async service."""
    calls = []

    async def service_handler(call):
        """Service handler coroutine."""
        calls.append(call)

    hass.services.async_register(
        "test_domain", "register_calls", functools.partial(service_handler)
    )
    await hass.async_block_till_done()

    await hass.services.async_call("test_domain", "REGISTER_CALLS", blocking=True)
    assert len(calls) == 1


async def test_serviceregistry_callback_service(hass: HomeAssistant) -> None:
    """Test registering and calling an async service."""
    calls = []

    @ha.callback
    def service_handler(call):
        """Service handler coroutine."""
        calls.append(call)

    hass.services.async_register("test_domain", "register_calls", service_handler)

    await hass.services.async_call("test_domain", "REGISTER_CALLS", blocking=True)
    assert len(calls) == 1


async def test_serviceregistry_remove_service(hass: HomeAssistant) -> None:
    """Test remove service."""
    calls_remove = async_capture_events(hass, EVENT_SERVICE_REMOVED)

    hass.services.async_register("test_domain", "test_service", lambda call: None)
    assert hass.services.has_service("test_Domain", "test_Service")

    hass.services.async_remove("test_Domain", "test_Service")
    await hass.async_block_till_done()

    assert not hass.services.has_service("test_Domain", "test_Service")
    assert len(calls_remove) == 1
    assert calls_remove[-1].data["domain"] == "test_domain"
    assert calls_remove[-1].data["service"] == "test_service"


async def test_serviceregistry_service_that_not_exists(hass: HomeAssistant) -> None:
    """Test remove service that not exists."""
    calls_remove = async_capture_events(hass, EVENT_SERVICE_REMOVED)
    assert not hass.services.has_service("test_xxx", "test_yyy")
    hass.services.async_remove("test_xxx", "test_yyy")
    await hass.async_block_till_done()
    assert len(calls_remove) == 0

    with pytest.raises(ServiceNotFound):
        await hass.services.async_call("test_do_not", "exist", {})


async def test_serviceregistry_async_service_raise_exception(
    hass: HomeAssistant,
) -> None:
    """Test registering and calling an async service raise exception."""

    async def service_handler(_):
        """Service handler coroutine."""
        raise ValueError

    hass.services.async_register("test_domain", "register_calls", service_handler)

    with pytest.raises(ValueError):
        await hass.services.async_call("test_domain", "REGISTER_CALLS", blocking=True)

    # Non-blocking service call never throw exception
    hass.services.async_call("test_domain", "REGISTER_CALLS", blocking=False)
    await hass.async_block_till_done()


async def test_serviceregistry_callback_service_raise_exception(
    hass: HomeAssistant,
) -> None:
    """Test registering and calling an callback service raise exception."""

    @ha.callback
    def service_handler(_):
        """Service handler coroutine."""
        raise ValueError

    hass.services.async_register("test_domain", "register_calls", service_handler)

    with pytest.raises(ValueError):
        await hass.services.async_call("test_domain", "REGISTER_CALLS", blocking=True)

    # Non-blocking service call never throw exception
    hass.services.async_call("test_domain", "REGISTER_CALLS", blocking=False)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "supports_response",
    [
        SupportsResponse.ONLY,
        SupportsResponse.OPTIONAL,
    ],
)
async def test_serviceregistry_async_return_response(
    hass: HomeAssistant, supports_response: SupportsResponse
) -> None:
    """Test service call for a service that returns response data."""

    async def service_handler(call: ServiceCall) -> ServiceResponse:
        """Service handler coroutine."""
        assert call.return_response
        return {"test-reply": "test-value1"}

    hass.services.async_register(
        "test_domain",
        "test_service",
        service_handler,
        supports_response=supports_response,
    )
    result = await hass.services.async_call(
        "test_domain",
        "test_service",
        service_data={},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    assert result == {"test-reply": "test-value1"}


async def test_services_call_return_response_requires_blocking(
    hass: HomeAssistant,
) -> None:
    """Test that non-blocking service calls cannot ask for response data."""
    async_mock_service(hass, "test_domain", "test_service")
    with pytest.raises(ValueError, match="when blocking=False"):
        await hass.services.async_call(
            "test_domain",
            "test_service",
            service_data={},
            blocking=False,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("response_data", "expected_error"),
    [
        (True, "expected a dictionary"),
        (False, "expected a dictionary"),
        (None, "expected a dictionary"),
        ("some-value", "expected a dictionary"),
        (["some-list"], "expected a dictionary"),
    ],
)
async def test_serviceregistry_return_response_invalid(
    hass: HomeAssistant, response_data: Any, expected_error: str
) -> None:
    """Test service call response data must be json serializable objects."""

    def service_handler(call: ServiceCall) -> ServiceResponse:
        """Service handler coroutine."""
        assert call.return_response
        return response_data

    hass.services.async_register(
        "test_domain",
        "test_service",
        service_handler,
        supports_response=SupportsResponse.ONLY,
    )
    with pytest.raises(HomeAssistantError, match=expected_error):
        await hass.services.async_call(
            "test_domain",
            "test_service",
            service_data={},
            blocking=True,
            return_response=True,
        )
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("supports_response", "return_response", "expected_error"),
    [
        (SupportsResponse.NONE, True, "not support responses"),
        (SupportsResponse.ONLY, False, "caller did not ask for responses"),
    ],
)
async def test_serviceregistry_return_response_arguments(
    hass: HomeAssistant,
    supports_response: SupportsResponse,
    return_response: bool,
    expected_error: str,
) -> None:
    """Test service call response data invalid arguments."""

    hass.services.async_register(
        "test_domain",
        "test_service",
        "service_handler",
        supports_response=supports_response,
    )

    with pytest.raises(ValueError, match=expected_error):
        await hass.services.async_call(
            "test_domain",
            "test_service",
            service_data={},
            blocking=True,
            return_response=return_response,
        )


@pytest.mark.parametrize(
    ("return_response", "expected_response_data"),
    [
        (True, {"key": "value"}),
        (False, None),
    ],
)
async def test_serviceregistry_return_response_optional(
    hass: HomeAssistant,
    return_response: bool,
    expected_response_data: Any,
) -> None:
    """Test optional service call response data."""

    def service_handler(call: ServiceCall) -> ServiceResponse:
        """Service handler coroutine."""
        if call.return_response:
            return {"key": "value"}
        return None

    hass.services.async_register(
        "test_domain",
        "test_service",
        service_handler,
        supports_response=SupportsResponse.OPTIONAL,
    )
    response_data = await hass.services.async_call(
        "test_domain",
        "test_service",
        service_data={},
        blocking=True,
        return_response=return_response,
    )
    await hass.async_block_till_done()
    assert response_data == expected_response_data


async def test_config_defaults() -> None:
    """Test config defaults."""
    hass = Mock()
    config = ha.Config(hass)
    assert config.hass is hass
    assert config.latitude == 0
    assert config.longitude == 0
    assert config.elevation == 0
    assert config.location_name == "Home"
    assert config.time_zone == "UTC"
    assert config.internal_url is None
    assert config.external_url is None
    assert config.config_source is ha.ConfigSource.DEFAULT
    assert config.skip_pip is False
    assert config.skip_pip_packages == []
    assert config.components == set()
    assert config.api is None
    assert config.config_dir is None
    assert config.allowlist_external_dirs == set()
    assert config.allowlist_external_urls == set()
    assert config.media_dirs == {}
    assert config.safe_mode is False
    assert config.legacy_templates is False
    assert config.currency == "EUR"
    assert config.country is None
    assert config.language == "en"


async def test_config_path_with_file() -> None:
    """Test get_config_path method."""
    config = ha.Config(None)
    config.config_dir = "/test/ha-config"
    assert config.path("test.conf") == "/test/ha-config/test.conf"


async def test_config_path_with_dir_and_file() -> None:
    """Test get_config_path method."""
    config = ha.Config(None)
    config.config_dir = "/test/ha-config"
    assert config.path("dir", "test.conf") == "/test/ha-config/dir/test.conf"


async def test_config_as_dict() -> None:
    """Test as dict."""
    config = ha.Config(None)
    config.config_dir = "/test/ha-config"
    config.hass = MagicMock()
    type(config.hass.state).value = PropertyMock(return_value="RUNNING")
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
        "allowlist_external_dirs": set(),
        "allowlist_external_urls": set(),
        "version": __version__,
        "config_source": ha.ConfigSource.DEFAULT,
        "safe_mode": False,
        "state": "RUNNING",
        "external_url": None,
        "internal_url": None,
        "currency": "EUR",
        "country": None,
        "language": "en",
    }

    assert expected == config.as_dict()


async def test_config_is_allowed_path() -> None:
    """Test is_allowed_path method."""
    config = ha.Config(None)
    with TemporaryDirectory() as tmp_dir:
        # The created dir is in /tmp. This is a symlink on OS X
        # causing this test to fail unless we resolve path first.
        config.allowlist_external_dirs = {os.path.realpath(tmp_dir)}

        test_file = os.path.join(tmp_dir, "test.jpg")
        with open(test_file, "w") as tmp_file:
            tmp_file.write("test")

        valid = [test_file, tmp_dir, os.path.join(tmp_dir, "notfound321")]
        for path in valid:
            assert config.is_allowed_path(path)

        config.allowlist_external_dirs = {"/home", "/var"}

        invalid = [
            "/hass/config/secure",
            "/etc/passwd",
            "/root/secure_file",
            "/var/../etc/passwd",
            test_file,
        ]
        for path in invalid:
            assert not config.is_allowed_path(path)

        with pytest.raises(AssertionError):
            config.is_allowed_path(None)


async def test_config_is_allowed_external_url() -> None:
    """Test is_allowed_external_url method."""
    config = ha.Config(None)
    config.allowlist_external_urls = [
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
        assert config.is_allowed_external_url(url)

    invalid = [
        "https://a.co",
        "https://y.com/bla_wrong",
        "https://y.com/bla/../image.jpg",
        "https://z.com/images",
    ]
    for url in invalid:
        assert not config.is_allowed_external_url(url)


async def test_event_on_update(hass: HomeAssistant) -> None:
    """Test that event is fired on update."""
    events = async_capture_events(hass, EVENT_CORE_CONFIG_UPDATE)

    assert hass.config.latitude != 12

    await hass.config.async_update(latitude=12)
    await hass.async_block_till_done()

    assert hass.config.latitude == 12
    assert len(events) == 1
    assert events[0].data == {"latitude": 12}


async def test_bad_timezone_raises_value_error(hass: HomeAssistant) -> None:
    """Test bad timezone raises ValueError."""
    with pytest.raises(ValueError):
        await hass.config.async_update(time_zone="not_a_timezone")


async def test_start_taking_too_long(
    event_loop, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when async_start takes too long."""
    hass = ha.HomeAssistant()
    caplog.set_level(logging.WARNING)
    hass.async_create_task(asyncio.sleep(0))

    try:
        with patch("asyncio.wait", return_value=(set(), {asyncio.Future()})):
            await hass.async_start()

        assert hass.state == ha.CoreState.running
        assert "Something is blocking Home Assistant" in caplog.text

    finally:
        await hass.async_stop()
        assert hass.state == ha.CoreState.stopped


async def test_service_executed_with_subservices(hass: HomeAssistant) -> None:
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
        await asyncio.wait(
            [
                hass.async_create_task(call1),
                hass.async_create_task(call2),
            ]
        )
        calls.append(call)

    hass.services.async_register("test", "outer", handle_outer)

    await hass.services.async_call("test", "outer", blocking=True, context=context)

    assert len(calls) == 4
    assert [call.service for call in calls] == ["outer", "inner", "inner", "outer"]
    assert all(call.context is context for call in calls)


async def test_service_call_event_contains_original_data(hass: HomeAssistant) -> None:
    """Test that service call event contains original data."""
    events = async_capture_events(hass, EVENT_CALL_SERVICE)

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


def test_context() -> None:
    """Test context init."""
    c = ha.Context()
    assert c.user_id is None
    assert c.parent_id is None
    assert c.id is not None

    c = ha.Context(23, 100)
    assert c.user_id == 23
    assert c.parent_id == 100
    assert c.id is not None


async def test_async_functions_with_callback(hass: HomeAssistant) -> None:
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


def test_valid_entity_id() -> None:
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


def test_valid_domain() -> None:
    """Test valid domain."""
    for invalid in [
        "_light",
        ".kitchen",
        ".light.kitchen",
        "light_.kitchen",
        "._kitchen",
        "light.",
        "light.kitchen__ceiling",
        "light.kitchen_yo_",
        "light.kitchen.",
        "Light",
    ]:
        assert not ha.valid_domain(invalid), invalid

    for valid in [
        "1",
        "1light",
        "a",
        "input_boolean",
        "light",
    ]:
        assert ha.valid_domain(valid), valid


async def test_additional_data_in_core_config(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test that we can handle additional data in core configuration."""
    config = ha.Config(hass)
    hass_storage[ha.CORE_STORAGE_KEY] = {
        "version": 1,
        "data": {"location_name": "Test Name", "additional_valid_key": "value"},
    }
    await config.async_load()
    assert config.location_name == "Test Name"


async def test_incorrect_internal_external_url(
    hass: HomeAssistant, hass_storage: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Test that we warn when detecting invalid internal/external url."""
    config = ha.Config(hass)

    hass_storage[ha.CORE_STORAGE_KEY] = {
        "version": 1,
        "data": {
            "internal_url": None,
            "external_url": None,
        },
    }
    await config.async_load()
    assert "Invalid external_url set" not in caplog.text
    assert "Invalid internal_url set" not in caplog.text

    config = ha.Config(hass)

    hass_storage[ha.CORE_STORAGE_KEY] = {
        "version": 1,
        "data": {
            "internal_url": "https://community.home-assistant.io/profile",
            "external_url": "https://www.home-assistant.io/blue",
        },
    }
    await config.async_load()
    assert "Invalid external_url set" in caplog.text
    assert "Invalid internal_url set" in caplog.text


async def test_start_events(hass: HomeAssistant) -> None:
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


async def test_log_blocking_events(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure we log which task is blocking startup when debug logging is on."""
    caplog.set_level(logging.DEBUG)

    async def _wait_a_bit_1():
        await asyncio.sleep(0.1)

    async def _wait_a_bit_2():
        await asyncio.sleep(0.1)

    hass.async_create_task(_wait_a_bit_1())
    await hass.async_block_till_done()

    with patch.object(ha, "BLOCK_LOG_TIMEOUT", 0.0001):
        hass.async_create_task(_wait_a_bit_2())
        await hass.async_block_till_done()

    assert "_wait_a_bit_2" in caplog.text
    assert "_wait_a_bit_1" not in caplog.text


async def test_chained_logging_hits_log_timeout(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure we log which task is blocking startup when there is a task chain and debug logging is on."""
    caplog.set_level(logging.DEBUG)

    created = 0

    async def _task_chain_1():
        nonlocal created
        created += 1
        if created > 1000:
            return
        hass.async_create_task(_task_chain_2())

    async def _task_chain_2():
        nonlocal created
        created += 1
        if created > 1000:
            return
        hass.async_create_task(_task_chain_1())

    with patch.object(ha, "BLOCK_LOG_TIMEOUT", 0.0001):
        hass.async_create_task(_task_chain_1())
        await hass.async_block_till_done()

    assert "_task_chain_" in caplog.text


async def test_chained_logging_misses_log_timeout(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure we do not log which task is blocking startup if we do not hit the timeout."""
    caplog.set_level(logging.DEBUG)

    created = 0

    async def _task_chain_1():
        nonlocal created
        created += 1
        if created > 10:
            return
        hass.async_create_task(_task_chain_2())

    async def _task_chain_2():
        nonlocal created
        created += 1
        if created > 10:
            return
        hass.async_create_task(_task_chain_1())

    hass.async_create_task(_task_chain_1())
    await hass.async_block_till_done()

    assert "_task_chain_" not in caplog.text


async def test_async_all(hass: HomeAssistant) -> None:
    """Test async_all."""

    hass.states.async_set("switch.link", "on")
    hass.states.async_set("light.bowl", "on")
    hass.states.async_set("light.frog", "on")
    hass.states.async_set("vacuum.floor", "on")

    assert {state.entity_id for state in hass.states.async_all()} == {
        "switch.link",
        "light.bowl",
        "light.frog",
        "vacuum.floor",
    }
    assert {state.entity_id for state in hass.states.async_all("light")} == {
        "light.bowl",
        "light.frog",
    }
    assert {
        state.entity_id for state in hass.states.async_all(["light", "switch"])
    } == {"light.bowl", "light.frog", "switch.link"}


async def test_async_entity_ids_count(hass: HomeAssistant) -> None:
    """Test async_entity_ids_count."""

    hass.states.async_set("switch.link", "on")
    hass.states.async_set("light.bowl", "on")
    hass.states.async_set("light.frog", "on")
    hass.states.async_set("vacuum.floor", "on")

    assert hass.states.async_entity_ids_count() == 4
    assert hass.states.async_entity_ids_count("light") == 2

    hass.states.async_set("light.cow", "on")

    assert hass.states.async_entity_ids_count() == 5
    assert hass.states.async_entity_ids_count("light") == 3


async def test_hassjob_forbid_coroutine() -> None:
    """Test hassjob forbids coroutines."""

    async def bla():
        pass

    coro = bla()

    with pytest.raises(ValueError):
        ha.HassJob(coro)

    # To avoid warning about unawaited coro
    await coro


async def test_reserving_states(hass: HomeAssistant) -> None:
    """Test we can reserve a state in the state machine."""

    hass.states.async_reserve("light.bedroom")
    assert hass.states.async_available("light.bedroom") is False
    hass.states.async_set("light.bedroom", "on")
    assert hass.states.async_available("light.bedroom") is False

    with pytest.raises(ha.HomeAssistantError):
        hass.states.async_reserve("light.bedroom")

    hass.states.async_remove("light.bedroom")
    assert hass.states.async_available("light.bedroom") is True
    hass.states.async_set("light.bedroom", "on")

    with pytest.raises(ha.HomeAssistantError):
        hass.states.async_reserve("light.bedroom")

    assert hass.states.async_available("light.bedroom") is False
    hass.states.async_remove("light.bedroom")
    assert hass.states.async_available("light.bedroom") is True


def _ulid_timestamp(ulid: str) -> int:
    encoded = ulid[:10].encode("ascii")
    # This unpacks the time from the ulid

    # Copied from
    # https://github.com/ahawker/ulid/blob/06289583e9de4286b4d80b4ad000d137816502ca/ulid/base32.py#L296
    decoding = array.array(
        "B",
        (
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0x00,
            0x01,
            0x02,
            0x03,
            0x04,
            0x05,
            0x06,
            0x07,
            0x08,
            0x09,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0x0A,
            0x0B,
            0x0C,
            0x0D,
            0x0E,
            0x0F,
            0x10,
            0x11,
            0x01,
            0x12,
            0x13,
            0x01,
            0x14,
            0x15,
            0x00,
            0x16,
            0x17,
            0x18,
            0x19,
            0x1A,
            0xFF,
            0x1B,
            0x1C,
            0x1D,
            0x1E,
            0x1F,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0x0A,
            0x0B,
            0x0C,
            0x0D,
            0x0E,
            0x0F,
            0x10,
            0x11,
            0x01,
            0x12,
            0x13,
            0x01,
            0x14,
            0x15,
            0x00,
            0x16,
            0x17,
            0x18,
            0x19,
            0x1A,
            0xFF,
            0x1B,
            0x1C,
            0x1D,
            0x1E,
            0x1F,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
            0xFF,
        ),
    )
    return int.from_bytes(
        bytes(
            (
                ((decoding[encoded[0]] << 5) | decoding[encoded[1]]) & 0xFF,
                ((decoding[encoded[2]] << 3) | (decoding[encoded[3]] >> 2)) & 0xFF,
                (
                    (decoding[encoded[3]] << 6)
                    | (decoding[encoded[4]] << 1)
                    | (decoding[encoded[5]] >> 4)
                )
                & 0xFF,
                ((decoding[encoded[5]] << 4) | (decoding[encoded[6]] >> 1)) & 0xFF,
                (
                    (decoding[encoded[6]] << 7)
                    | (decoding[encoded[7]] << 2)
                    | (decoding[encoded[8]] >> 3)
                )
                & 0xFF,
                ((decoding[encoded[8]] << 5) | (decoding[encoded[9]])) & 0xFF,
            )
        ),
        byteorder="big",
    )


async def test_state_change_events_context_id_match_state_time(
    hass: HomeAssistant,
) -> None:
    """Test last_updated, timed_fired, and the ulid all have the same time."""
    events = async_capture_events(hass, ha.EVENT_STATE_CHANGED)
    hass.states.async_set("light.bedroom", "on")
    await hass.async_block_till_done()
    state: State = hass.states.get("light.bedroom")
    assert state.last_updated == events[0].time_fired
    assert len(state.context.id) == 26
    # ULIDs store time to 3 decimal places compared to python timestamps
    assert _ulid_timestamp(state.context.id) == int(
        state.last_updated.timestamp() * 1000
    )


async def test_state_firing_event_matches_context_id_ulid_time(
    hass: HomeAssistant,
) -> None:
    """Test timed_fired and the ulid have the same time."""
    events = async_capture_events(hass, EVENT_HOMEASSISTANT_STARTED)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    event = events[0]
    assert len(event.context.id) == 26
    # ULIDs store time to 3 decimal places compared to python timestamps
    assert _ulid_timestamp(event.context.id) == int(
        events[0].time_fired.timestamp() * 1000
    )


async def test_event_context(hass: HomeAssistant) -> None:
    """Test we can lookup the origin of a context from an event."""
    events = []

    @ha.callback
    def capture_events(event):
        nonlocal events
        events.append(event)

    cancel = hass.bus.async_listen("dummy_event", capture_events)
    cancel2 = hass.bus.async_listen("dummy_event_2", capture_events)

    hass.bus.async_fire("dummy_event")
    await hass.async_block_till_done()

    dummy_event: ha.Event = events[0]

    hass.bus.async_fire("dummy_event_2", context=dummy_event.context)
    await hass.async_block_till_done()
    context_id = dummy_event.context.id

    dummy_event2: ha.Event = events[1]
    assert dummy_event2.context == dummy_event.context
    assert dummy_event2.context.id == context_id
    cancel()
    cancel2()

    assert dummy_event2.context.origin_event == dummy_event


def _get_full_name(obj) -> str:
    """Get the full name of an object in memory."""
    objtype = type(obj)
    name = objtype.__name__
    if module := getattr(objtype, "__module__", None):
        return f"{module}.{name}"
    return name


def _get_by_type(full_name: str) -> list[Any]:
    """Get all objects in memory with a specific type."""
    return [obj for obj in gc.get_objects() if _get_full_name(obj) == full_name]


# The logger will hold a strong reference to the event for the life of the tests
# so we must patch it out
@pytest.mark.skipif(
    not os.environ.get("DEBUG_MEMORY"),
    reason="Takes too long on the CI",
)
@patch.object(ha._LOGGER, "debug", lambda *args: None)
async def test_state_changed_events_to_not_leak_contexts(hass: HomeAssistant) -> None:
    """Test state changed events do not leak contexts."""
    gc.collect()
    # Other tests can log Contexts which keep them in memory
    # so we need to look at how many exist at the start
    init_count = len(_get_by_type("homeassistant.core.Context"))

    assert len(_get_by_type("homeassistant.core.Context")) == init_count
    for i in range(20):
        hass.states.async_set("light.switch", str(i))
    await hass.async_block_till_done()
    gc.collect()

    assert len(_get_by_type("homeassistant.core.Context")) == init_count + 2

    hass.states.async_remove("light.switch")
    await hass.async_block_till_done()
    gc.collect()

    assert len(_get_by_type("homeassistant.core.Context")) == init_count


async def test_background_task(hass: HomeAssistant) -> None:
    """Test background tasks being quit."""
    result = asyncio.Future()

    async def test_task():
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            result.set_result(hass.state)
            raise

    task = hass.async_create_background_task(test_task(), "happy task")
    assert "happy task" in str(task)
    await asyncio.sleep(0)
    await hass.async_stop()
    assert result.result() == ha.CoreState.stopping


async def test_shutdown_does_not_block_on_normal_tasks(
    hass: HomeAssistant,
) -> None:
    """Ensure shutdown does not block on normal tasks."""
    result = asyncio.Future()
    unshielded_task = asyncio.sleep(10)

    async def test_task():
        try:
            await unshielded_task
        except asyncio.CancelledError:
            result.set_result(hass.state)

    start = time.monotonic()
    task = hass.async_create_task(test_task())
    await asyncio.sleep(0)
    await hass.async_stop()
    await asyncio.sleep(0)
    assert result.done()
    assert task.done()
    assert time.monotonic() - start < 0.5


async def test_shutdown_does_not_block_on_shielded_tasks(
    hass: HomeAssistant,
) -> None:
    """Ensure shutdown does not block on shielded tasks."""
    result = asyncio.Future()
    sleep_task = asyncio.ensure_future(asyncio.sleep(10))
    shielded_task = asyncio.shield(sleep_task)

    async def test_task():
        try:
            await shielded_task
        except asyncio.CancelledError:
            result.set_result(hass.state)

    start = time.monotonic()
    task = hass.async_create_task(test_task())
    await asyncio.sleep(0)
    await hass.async_stop()
    await asyncio.sleep(0)
    assert result.done()
    assert task.done()
    assert time.monotonic() - start < 0.5

    # Cleanup lingering task after test is done
    sleep_task.cancel()


async def test_cancellable_hassjob(hass: HomeAssistant) -> None:
    """Simulate a shutdown, ensure cancellable jobs are cancelled."""
    job = MagicMock()

    @ha.callback
    def run_job(job: HassJob) -> None:
        """Call the action."""
        hass.async_run_hass_job(job)

    timer1 = hass.loop.call_later(
        60, run_job, HassJob(ha.callback(job), cancel_on_shutdown=True)
    )
    timer2 = hass.loop.call_later(60, run_job, HassJob(ha.callback(job)))

    await hass.async_stop()

    assert timer1.cancelled()
    assert not timer2.cancelled()

    # Cleanup
    timer2.cancel()
