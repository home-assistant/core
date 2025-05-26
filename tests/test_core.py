"""Test to verify that Home Assistant core works."""

from __future__ import annotations

import array
import asyncio
from datetime import datetime, timedelta
import functools
import gc
import logging
import os
import re
import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun import freeze_time
import pytest
from pytest_unordered import unordered
import voluptuous as vol

from homeassistant import core as ha
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
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
    EVENT_STATE_REPORTED,
    MATCH_ALL,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CoreState,
    HassJob,
    HomeAssistant,
    ReleaseChannel,
    ServiceCall,
    ServiceResponse,
    State,
    SupportsResponse,
    callback,
    get_release_channel,
)
from homeassistant.core_config import Config
from homeassistant.exceptions import (
    HomeAssistantError,
    InvalidEntityFormatError,
    InvalidStateError,
    MaxLengthExceeded,
    ServiceNotFound,
    ServiceValidationError,
)
from homeassistant.helpers.json import json_dumps
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.read_only_dict import ReadOnlyDict

from .common import (
    async_capture_events,
    async_mock_service,
    help_test_all,
    import_and_test_deprecated_alias,
)

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


async def test_async_add_hass_job_schedule_callback() -> None:
    """Test that we schedule callbacks and add jobs to the job pool."""
    hass = MagicMock()
    job = MagicMock()

    ha.HomeAssistant._async_add_hass_job(hass, ha.HassJob(ha.callback(job)))
    assert len(hass.loop.call_soon.mock_calls) == 1
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.add_job.mock_calls) == 0


async def test_async_add_hass_job_eager_start_coro_suspends(
    hass: HomeAssistant,
) -> None:
    """Test scheduling a coro as a task that will suspend with eager_start."""

    async def job_that_suspends():
        await asyncio.sleep(0)

    task = hass._async_add_hass_job(ha.HassJob(ha.callback(job_that_suspends)))
    assert not task.done()
    assert task in hass._tasks
    await task
    assert task not in hass._tasks


async def test_async_run_hass_job_eager_start_coro_suspends(
    hass: HomeAssistant,
) -> None:
    """Test scheduling a coro as a task that will suspend with eager_start."""

    async def job_that_suspends():
        await asyncio.sleep(0)

    task = hass.async_run_hass_job(ha.HassJob(ha.callback(job_that_suspends)))
    assert not task.done()
    assert task in hass._tasks
    await task
    assert task not in hass._tasks


async def test_async_add_hass_job_background(hass: HomeAssistant) -> None:
    """Test scheduling a coro as a background task with async_add_hass_job."""

    async def job_that_suspends():
        await asyncio.sleep(0)

    task = hass._async_add_hass_job(
        ha.HassJob(ha.callback(job_that_suspends)), background=True
    )
    assert not task.done()
    assert task in hass._background_tasks
    await task
    assert task not in hass._background_tasks


async def test_async_run_hass_job_background(hass: HomeAssistant) -> None:
    """Test scheduling a coro as a background task with async_run_hass_job."""

    async def job_that_suspends():
        await asyncio.sleep(0)

    task = hass.async_run_hass_job(
        ha.HassJob(ha.callback(job_that_suspends)), background=True
    )
    assert not task.done()
    assert task in hass._background_tasks
    await task
    assert task not in hass._background_tasks


async def test_async_add_hass_job_eager_background(hass: HomeAssistant) -> None:
    """Test scheduling a coro as an eager background task with async_add_hass_job."""

    async def job_that_suspends():
        await asyncio.sleep(0)

    task = hass._async_add_hass_job(
        ha.HassJob(ha.callback(job_that_suspends)), background=True
    )
    assert not task.done()
    assert task in hass._background_tasks
    await task
    assert task not in hass._background_tasks


async def test_async_run_hass_job_eager_background(hass: HomeAssistant) -> None:
    """Test scheduling a coro as an eager background task with async_run_hass_job."""

    async def job_that_suspends():
        await asyncio.sleep(0)

    task = hass.async_run_hass_job(
        ha.HassJob(ha.callback(job_that_suspends)), background=True
    )
    assert not task.done()
    assert task in hass._background_tasks
    await task
    assert task not in hass._background_tasks


async def test_async_run_hass_job_background_synchronous(hass: HomeAssistant) -> None:
    """Test scheduling a coro as an eager background task with async_run_hass_job."""

    async def job_that_does_not_suspends():
        pass

    task = hass.async_run_hass_job(
        ha.HassJob(ha.callback(job_that_does_not_suspends)),
        background=True,
    )
    assert task.done()
    assert task not in hass._background_tasks
    assert task not in hass._tasks
    await task


async def test_async_run_hass_job_synchronous(hass: HomeAssistant) -> None:
    """Test scheduling a coro as an eager task with async_run_hass_job."""

    async def job_that_does_not_suspends():
        pass

    task = hass.async_run_hass_job(
        ha.HassJob(ha.callback(job_that_does_not_suspends)),
        background=False,
    )
    assert task.done()
    assert task not in hass._background_tasks
    assert task not in hass._tasks
    await task


async def test_async_add_hass_job_coro_named(hass: HomeAssistant) -> None:
    """Test that we schedule coroutines and add jobs to the job pool with a name."""

    async def mycoro():
        pass

    job = ha.HassJob(mycoro, "named coro")
    assert "named coro" in str(job)
    assert job.name == "named coro"
    task = ha.HomeAssistant._async_add_hass_job(hass, job)
    assert "named coro" in str(task)


async def test_async_add_hass_job_eager_start(hass: HomeAssistant) -> None:
    """Test eager_start with async_add_hass_job."""

    async def mycoro():
        pass

    job = ha.HassJob(mycoro, "named coro")
    assert "named coro" in str(job)
    assert job.name == "named coro"
    task = ha.HomeAssistant._async_add_hass_job(hass, job)
    assert "named coro" in str(task)


async def test_async_add_hass_job_schedule_partial_callback() -> None:
    """Test that we schedule partial coros and add jobs to the job pool."""
    hass = MagicMock()
    job = MagicMock()
    partial = functools.partial(ha.callback(job))

    ha.HomeAssistant._async_add_hass_job(hass, ha.HassJob(partial))
    assert len(hass.loop.call_soon.mock_calls) == 1
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.add_job.mock_calls) == 0


async def test_async_add_hass_job_schedule_corofunction_eager_start() -> None:
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=asyncio.get_running_loop()))

    async def job():
        pass

    with patch(
        "homeassistant.core.create_eager_task", wraps=create_eager_task
    ) as mock_create_eager_task:
        hass_job = ha.HassJob(job)
        task = ha.HomeAssistant._async_add_hass_job(hass, hass_job)
        assert len(hass.loop.call_soon.mock_calls) == 0
        assert len(hass.add_job.mock_calls) == 0
        assert mock_create_eager_task.mock_calls
        await task


async def test_async_add_hass_job_schedule_partial_corofunction_eager_start() -> None:
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=asyncio.get_running_loop()))

    async def job():
        pass

    partial = functools.partial(job)

    with patch(
        "homeassistant.core.create_eager_task", wraps=create_eager_task
    ) as mock_create_eager_task:
        hass_job = ha.HassJob(partial)
        task = ha.HomeAssistant._async_add_hass_job(hass, hass_job)
        assert len(hass.loop.call_soon.mock_calls) == 0
        assert len(hass.add_job.mock_calls) == 0
        assert mock_create_eager_task.mock_calls
        await task


async def test_async_add_job_add_hass_threaded_job_to_pool() -> None:
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock()

    def job():
        pass

    ha.HomeAssistant._async_add_hass_job(hass, ha.HassJob(job))
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.loop.run_in_executor.mock_calls) == 2


async def test_async_create_task_schedule_coroutine() -> None:
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=asyncio.get_running_loop()))

    async def job():
        pass

    ha.HomeAssistant.async_create_task_internal(hass, job(), eager_start=False)
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0


async def test_async_create_task_eager_start_schedule_coroutine() -> None:
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=asyncio.get_running_loop()))

    async def job():
        pass

    ha.HomeAssistant.async_create_task_internal(hass, job(), eager_start=True)
    # Should create the task directly since 3.12 supports eager_start
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.add_job.mock_calls) == 0


async def test_async_create_task_schedule_coroutine_with_name() -> None:
    """Test that we schedule coroutines and add jobs to the job pool with a name."""
    hass = MagicMock(loop=MagicMock(wraps=asyncio.get_running_loop()))

    async def job():
        pass

    task = ha.HomeAssistant.async_create_task_internal(
        hass, job(), "named task", eager_start=False
    )
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0
    assert "named task" in str(task)


async def test_async_run_eager_hass_job_calls_callback() -> None:
    """Test that the callback annotation is respected."""
    hass = MagicMock()
    calls = []

    def job():
        asyncio.get_running_loop()  # ensure we are in the event loop
        calls.append(1)

    ha.HomeAssistant.async_run_hass_job(hass, ha.HassJob(ha.callback(job)))
    assert len(calls) == 1


async def test_async_run_eager_hass_job_calls_coro_function() -> None:
    """Test running coros from async_run_hass_job with eager_start."""
    hass = MagicMock()

    async def job():
        pass

    ha.HomeAssistant.async_run_hass_job(hass, ha.HassJob(job))
    assert len(hass._async_add_hass_job.mock_calls) == 1


async def test_async_run_hass_job_calls_callback() -> None:
    """Test that the callback annotation is respected."""
    hass = MagicMock()
    calls = []

    def job():
        calls.append(1)

    ha.HomeAssistant.async_run_hass_job(hass, ha.HassJob(ha.callback(job)))
    assert len(calls) == 1
    assert len(hass.async_add_job.mock_calls) == 0


async def test_async_run_hass_job_delegates_non_async() -> None:
    """Test that the callback annotation is respected."""
    hass = MagicMock()
    calls = []

    def job():
        calls.append(1)

    ha.HomeAssistant.async_run_hass_job(hass, ha.HassJob(job))
    assert len(calls) == 0
    assert len(hass._async_add_hass_job.mock_calls) == 1


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
            raise Exception  # noqa: TRY002
        except HomeAssistantError:
            return False

        raise Exception  # noqa: TRY002

    # Test scheduling a coroutine which calls async_get_hass via hass.async_create_task
    async def _async_create_task() -> None:
        task_finished.set()
        assert can_call_async_get_hass()

    hass.async_create_task(_async_create_task(), "create_task")
    async with asyncio.timeout(1):
        await task_finished.wait()
    task_finished.clear()

    # Test scheduling a callback which calls async_get_hass via hass.async_add_job
    @callback
    def _add_job() -> None:
        assert can_call_async_get_hass()
        task_finished.set()

    hass.async_add_job(_add_job)
    async with asyncio.timeout(1):
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
    async with asyncio.timeout(1):
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
    async with asyncio.timeout(1):
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
    async with asyncio.timeout(1):
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
    async with asyncio.timeout(1):
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
    async with asyncio.timeout(1):
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
    async with asyncio.timeout(1):
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
    async with asyncio.timeout(1):
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
    async with asyncio.timeout(1):
        await task_finished.wait()
    task_finished.clear()
    my_job_create_task.join()


async def test_async_add_executor_job_background(hass: HomeAssistant) -> None:
    """Test running an executor job in the background."""
    calls = []

    def job():
        time.sleep(0.01)
        calls.append(1)

    async def _async_add_executor_job():
        await hass.async_add_executor_job(job)

    task = hass.async_create_background_task(
        _async_add_executor_job(), "background", eager_start=True
    )
    await hass.async_block_till_done()
    assert len(calls) == 0
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(calls) == 1
    await task


async def test_async_add_executor_job(hass: HomeAssistant) -> None:
    """Test running an executor job."""
    calls = []

    def job():
        time.sleep(0.01)
        calls.append(1)

    async def _async_add_executor_job():
        await hass.async_add_executor_job(job)

    task = hass.async_create_task(
        _async_add_executor_job(), "background", eager_start=True
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    await task


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


async def test_stage_shutdown_timeouts(hass: HomeAssistant) -> None:
    """Simulate a shutdown, test timeouts at each step."""

    with patch.object(hass.timeout, "async_timeout", side_effect=TimeoutError):
        await hass.async_stop()

    assert hass.state is CoreState.stopped


async def test_stage_shutdown_generic_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Simulate a shutdown, test that a generic error at the final stage doesn't prevent it."""

    task = asyncio.Future()
    hass._tasks.add(task)

    def fail_the_task(_):
        task.set_exception(Exception("test_exception"))

    with patch.object(task, "cancel", side_effect=fail_the_task) as patched_call:
        await hass.async_stop()
        assert patched_call.called

    assert "test_exception" in caplog.text
    assert hass.state == ha.CoreState.stopped


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

    async def _record_block_till_done(wait_background_tasks: bool = False):
        nonlocal stop_calls
        stop_calls.append("async_block_till_done")

    def _record_shutdown_run_callback_threadsafe(loop):
        nonlocal stop_calls
        stop_calls.append(("shutdown_run_callback_threadsafe", loop))

    with (
        patch.object(hass, "async_block_till_done", _record_block_till_done),
        patch(
            "homeassistant.core.shutdown_run_callback_threadsafe",
            _record_shutdown_run_callback_threadsafe,
        ),
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


def test_add_job_pending_tasks_coro(hass: HomeAssistant) -> None:
    """Add a coro to pending tasks."""

    async def test_coro():
        """Test Coro."""

    for _ in range(2):
        hass.add_job(test_coro())

    # Ensure add_job does not run immediately
    assert len(hass._tasks) == 0


async def test_async_add_job_pending_tasks_coro(hass: HomeAssistant) -> None:
    """Add a coro to pending tasks."""
    call_count = []

    async def test_coro():
        """Test Coro."""
        call_count.append("call")

    for _ in range(2):
        hass.async_add_job(test_coro())

    assert len(hass._tasks) == 2
    await hass.async_block_till_done()
    assert len(call_count) == 2
    assert len(hass._tasks) == 0


async def test_async_create_task_pending_tasks_coro(hass: HomeAssistant) -> None:
    """Add a coro to pending tasks."""
    call_count = []

    async def test_coro():
        """Test Coro."""
        call_count.append("call")

    for _ in range(2):
        hass.async_create_task(test_coro(), eager_start=False)

    assert len(hass._tasks) == 2
    await hass.async_block_till_done()
    assert len(call_count) == 2
    assert len(hass._tasks) == 0


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
        ha.Event(
            "some_type", data, time_fired_timestamp=now.timestamp(), context=context
        )
        for _ in range(2)
    )

    assert event1.as_dict() == event2.as_dict()


def test_event_time() -> None:
    """Test time_fired and time_fired_timestamp."""
    now = dt_util.utcnow()
    event = ha.Event(
        "some_type", {"some": "attr"}, time_fired_timestamp=now.timestamp()
    )
    assert event.time_fired_timestamp == now.timestamp()
    assert event.time_fired == now


def test_event_json_fragment() -> None:
    """Test event JSON fragments."""
    now = dt_util.utcnow()
    data = {"some": "attr"}
    context = ha.Context()
    event1, event2 = (
        ha.Event(
            "some_type", data, time_fired_timestamp=now.timestamp(), context=context
        )
        for _ in range(2)
    )

    # We are testing that the JSON fragments are the same when as_dict is called
    # after json_fragment or before.
    json_fragment_1 = event1.json_fragment
    as_dict_1 = event1.as_dict()
    as_dict_2 = event2.as_dict()
    json_fragment_2 = event2.json_fragment

    assert json_dumps(json_fragment_1) == json_dumps(json_fragment_2)
    # We also test that the as_dict is the same
    assert as_dict_1 == as_dict_2

    # Finally we verify that the as_dict is a ReadOnlyDict
    # as is the data and context inside regardless of
    # if the json fragment was called first or not
    assert isinstance(as_dict_1, ReadOnlyDict)
    assert isinstance(as_dict_1["data"], ReadOnlyDict)
    assert isinstance(as_dict_1["context"], ReadOnlyDict)

    assert isinstance(as_dict_2, ReadOnlyDict)
    assert isinstance(as_dict_2["data"], ReadOnlyDict)
    assert isinstance(as_dict_2["context"], ReadOnlyDict)


def test_event_repr() -> None:
    """Test that Event repr method works."""
    assert str(ha.Event("TestEvent")) == "<Event TestEvent[L]>"

    assert (
        str(ha.Event("TestEvent", {"beer": "nice"}, ha.EventOrigin.remote))
        == "<Event TestEvent[R]: beer=nice>"
    )


def test_event_origin_idx() -> None:
    """Test the EventOrigin idx."""
    assert ha.EventOrigin.remote is ha.EventOrigin.remote
    assert ha.EventOrigin.local is ha.EventOrigin.local
    assert ha.EventOrigin.local.idx == 0
    assert ha.EventOrigin.remote.idx == 1


def test_event_as_dict() -> None:
    """Test an Event as dictionary."""
    event_type = "some_type"
    now = dt_util.utcnow()
    data = {"some": "attr"}

    event = ha.Event(event_type, data, ha.EventOrigin.local, now.timestamp())
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
        last_changed=last_time,
        last_reported=last_time,
        last_updated=last_time,
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
        "last_reported": last_time.isoformat(),
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
        context=ha.Context(id="01H0D6K3RFJAYAV2093ZW30PCW"),
        last_changed=last_time,
        last_reported=last_time,
        last_updated=last_time,
    )
    expected = (
        b'{"entity_id":"happy.happy","state":"on","attributes":{"pig":"dog"},'
        b'"last_changed":"1984-12-08T12:00:00","last_reported":"1984-12-08T12:00:00",'
        b'"last_updated":"1984-12-08T12:00:00",'
        b'"context":{"id":"01H0D6K3RFJAYAV2093ZW30PCW","parent_id":null,"user_id":null}}'
    )
    as_dict_json_1 = state.as_dict_json
    assert as_dict_json_1 == expected
    # 2nd time to verify cache
    assert state.as_dict_json == expected
    assert state.as_dict_json is as_dict_json_1


def test_state_json_fragment() -> None:
    """Test state JSON fragments."""
    last_time = datetime(1984, 12, 8, 12, 0, 0)
    state1, state2 = (
        ha.State(
            "happy.happy",
            "on",
            {"pig": "dog"},
            context=ha.Context(id="01H0D6K3RFJAYAV2093ZW30PCW"),
            last_changed=last_time,
            last_reported=last_time,
            last_updated=last_time,
        )
        for _ in range(2)
    )

    # We are testing that the JSON fragments are the same when as_dict is called
    # after json_fragment or before.
    json_fragment_1 = state1.json_fragment
    as_dict_1 = state1.as_dict()
    as_dict_2 = state2.as_dict()
    json_fragment_2 = state2.json_fragment

    assert json_dumps(json_fragment_1) == json_dumps(json_fragment_2)
    # We also test that the as_dict is the same
    assert as_dict_1 == as_dict_2

    # Finally we verify that the as_dict is a ReadOnlyDict
    # as is the attributes and context inside regardless of
    # if the json fragment was called first or not
    assert isinstance(as_dict_1, ReadOnlyDict)
    assert isinstance(as_dict_1["attributes"], ReadOnlyDict)
    assert isinstance(as_dict_1["context"], ReadOnlyDict)

    assert isinstance(as_dict_2, ReadOnlyDict)
    assert isinstance(as_dict_2["attributes"], ReadOnlyDict)
    assert isinstance(as_dict_2["context"], ReadOnlyDict)


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
    as_compressed_state = state.as_compressed_state
    # We are not too concerned about these being ReadOnlyDict
    # since we don't expect them to be called by external callers
    assert as_compressed_state == expected
    # 2nd time to verify cache
    assert state.as_compressed_state == expected


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
    as_compressed_state = state.as_compressed_state
    # We are not too concerned about these being ReadOnlyDict
    # since we don't expect them to be called by external callers
    assert as_compressed_state == expected
    # 2nd time to verify cache
    assert state.as_compressed_state == expected


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
    expected = b'"happy.happy":{"s":"on","a":{"pig":"dog"},"c":"01H0D6H5K3SZJ3XGDHED1TJ79N","lc":471355200.0}'
    as_compressed_state = state.as_compressed_state_json
    # We are not too concerned about these being ReadOnlyDict
    # since we don't expect them to be called by external callers
    assert as_compressed_state == expected
    # 2nd time to verify cache
    assert state.as_compressed_state_json == expected
    assert state.as_compressed_state_json is as_compressed_state


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
    def mock_filter(event_data):
        """Mock filter."""
        return not event_data["filtered"]

    unsub = hass.bus.async_listen("test", listener, event_filter=mock_filter)

    hass.bus.async_fire("test", {"filtered": True})
    await hass.async_block_till_done()

    assert len(calls) == 0

    hass.bus.async_fire("test", {"filtered": False})
    await hass.async_block_till_done()

    assert len(calls) == 1

    unsub()


async def test_eventbus_run_immediately_callback(hass: HomeAssistant) -> None:
    """Test we can call events immediately with a callback."""
    calls = []

    @ha.callback
    def listener(event):
        """Mock listener."""
        calls.append(event)

    unsub = hass.bus.async_listen("test", listener)

    hass.bus.async_fire("test", {"event": True})
    # No async_block_till_done here
    assert len(calls) == 1

    unsub()


async def test_eventbus_run_immediately_coro(hass: HomeAssistant) -> None:
    """Test we can call events immediately with a coro."""
    calls = []

    async def listener(event):
        """Mock listener."""
        calls.append(event)

    unsub = hass.bus.async_listen("test", listener)

    hass.bus.async_fire("test", {"event": True})
    # No async_block_till_done here
    assert len(calls) == 1

    unsub()


async def test_eventbus_listen_once_run_immediately_coro(hass: HomeAssistant) -> None:
    """Test we can call events immediately with a coro."""
    calls = []

    async def listener(event):
        """Mock listener."""
        calls.append(event)

    hass.bus.async_listen_once("test", listener)

    hass.bus.async_fire("test", {"event": True})
    # No async_block_till_done here
    assert len(calls) == 1


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

    # Without cached translations the translation key is returned
    with pytest.raises(MaxLengthExceeded) as exc_info:
        hass.bus.async_fire(long_evt_name)

    assert str(exc_info.value) == "max_length_exceeded"
    assert exc_info.value.property_name == "event_type"
    assert exc_info.value.max_length == 64
    assert exc_info.value.value == long_evt_name

    # Fetch translations
    await async_setup_component(hass, "homeassistant", {})

    # With cached translations the formatted message is returned
    with pytest.raises(MaxLengthExceeded) as exc_info:
        hass.bus.async_fire(long_evt_name)

    assert (
        str(exc_info.value)
        == f"Value {long_evt_name} for property event_type has a maximum length of 64 characters"
    )
    assert exc_info.value.property_name == "event_type"
    assert exc_info.value.max_length == 64
    assert exc_info.value.value == long_evt_name


def test_state_init() -> None:
    """Test state.init."""
    with pytest.raises(InvalidEntityFormatError):
        ha.State("invalid_entity_format", "test_state")


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
                last_changed=datetime(1984, 12, 8, 12, 0, 0),
            )
        )
        == "<state happy.happy=on; brightness=144 @ 1984-12-08T12:00:00+00:00>"
    )


async def test_statemachine_async_set_invalid_state(hass: HomeAssistant) -> None:
    """Test setting an invalid state with the async_set method."""
    with pytest.raises(
        InvalidStateError,
        match="Invalid state with length 256. State max length is 255 characters.",
    ):
        hass.states.async_set("light.bowl", "o" * 256, {})


async def test_statemachine_async_set_internal_invalid_state(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setting an invalid state with the async_set_internal method."""
    long_state = "o" * 256
    hass.states.async_set_internal(
        "light.bowl",
        long_state,
        {},
        force_update=False,
        context=None,
        state_info=None,
        timestamp=time.time(),
    )
    assert hass.states.get("light.bowl").state == STATE_UNKNOWN
    assert (
        "homeassistant.core",
        logging.ERROR,
        f"State {long_state} for light.bowl is longer than 255, "
        f"falling back to {STATE_UNKNOWN}",
    ) in caplog.record_tuples


async def test_statemachine_is_state(hass: HomeAssistant) -> None:
    """Test is_state method."""
    hass.states.async_set("light.bowl", "on", {})
    assert hass.states.is_state("light.Bowl", "on")
    assert not hass.states.is_state("light.Bowl", "off")
    assert not hass.states.is_state("light.Non_existing", "on")


async def test_statemachine_entity_ids(hass: HomeAssistant) -> None:
    """Test async_entity_ids method."""
    assert hass.states.async_entity_ids() == []
    assert hass.states.async_entity_ids("light") == []
    assert hass.states.async_entity_ids(("light", "switch", "other")) == []

    hass.states.async_set("light.bowl", "on", {})
    hass.states.async_set("SWITCH.AC", "off", {})
    assert hass.states.async_entity_ids() == unordered(["light.bowl", "switch.ac"])
    assert hass.states.async_entity_ids("light") == ["light.bowl"]
    assert hass.states.async_entity_ids(("light", "switch", "other")) == unordered(
        ["light.bowl", "switch.ac"]
    )

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


async def test_state_machine_case_insensitivity(hass: HomeAssistant) -> None:
    """Test setting and getting states entity_id insensitivity."""
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    hass.states.async_set("light.BOWL", "off")
    await hass.async_block_till_done()

    assert hass.states.is_state("light.bowl", "off")
    assert len(events) == 1

    hass.states.async_set("ligHT.Bowl", "on")
    assert hass.states.get("light.bowl").state == "on"

    hass.states.async_set("light.BOWL", "off")
    assert hass.states.get("light.BoWL").state == "off"

    hass.states.async_set("light.bowl", "on")
    assert hass.states.get("light.bowl").state == "on"


async def test_statemachine_last_changed_not_updated_on_same_state(
    hass: HomeAssistant,
) -> None:
    """Test to not update the existing, same state."""
    hass.states.async_set("light.bowl", "on", {})
    state = hass.states.get("light.Bowl")

    future = dt_util.utcnow() + timedelta(hours=10)

    with freeze_time(future):
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


async def test_statemachine_avoids_updating_attributes(hass: HomeAssistant) -> None:
    """Test async_set avoids recreating ReadOnly dicts when possible."""
    attrs = {"some_attr": "attr_value"}

    hass.states.async_set("light.bowl", "off", attrs)
    await hass.async_block_till_done()

    state = hass.states.get("light.bowl")
    assert state.attributes == attrs

    hass.states.async_set("light.bowl", "on", attrs)
    await hass.async_block_till_done()

    new_state = hass.states.get("light.bowl")
    assert new_state.attributes == attrs

    assert new_state.attributes is state.attributes
    assert isinstance(new_state.attributes, ReadOnlyDict)


def test_service_call_repr() -> None:
    """Test ServiceCall repr."""
    call = ha.ServiceCall(None, "homeassistant", "start")
    assert str(call) == f"<ServiceCall homeassistant.start (c:{call.context.id})>"

    call2 = ha.ServiceCall(None, "homeassistant", "start", {"fast": "yes"})
    assert (
        str(call2)
        == f"<ServiceCall homeassistant.start (c:{call2.context.id}): fast=yes>"
    )


async def test_service_registry_has_service(hass: HomeAssistant) -> None:
    """Test has_service method."""
    hass.services.async_register("test_domain", "test_service", lambda call: None)
    assert len(hass.services.async_services()) == 1
    assert hass.services.has_service("tesT_domaiN", "tesT_servicE")
    assert not hass.services.has_service("test_domain", "non_existing")
    assert not hass.services.has_service("non_existing", "test_service")


async def test_service_registry_service_enumeration(hass: HomeAssistant) -> None:
    """Test enumerating services methods."""
    hass.services.async_register("test_domain", "test_service", lambda call: None)
    services1 = hass.services.async_services()
    services2 = hass.services.async_services()
    assert len(services1) == 1
    assert services1 == services2
    assert services1 is not services2  # should be a copy

    services1 = hass.services.async_services_internal()
    services2 = hass.services.async_services_internal()
    assert len(services1) == 1
    assert services1 == services2
    assert services1 is services2  # should be the same object

    assert hass.services.async_services_for_domain("unknown") == {}

    services1 = hass.services.async_services_for_domain("test_domain")
    services2 = hass.services.async_services_for_domain("test_domain")
    assert len(services1) == 1
    assert services1 == services2
    assert services1 is not services2  # should be a copy


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
    with pytest.raises(ServiceNotFound):
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
    await async_setup_component(hass, "homeassistant", {})
    calls_remove = async_capture_events(hass, EVENT_SERVICE_REMOVED)
    assert not hass.services.has_service("test_xxx", "test_yyy")
    hass.services.async_remove("test_xxx", "test_yyy")
    await hass.async_block_till_done()
    assert len(calls_remove) == 0

    with pytest.raises(ServiceNotFound) as exc:
        await hass.services.async_call("test_do_not", "exist", {})
    assert exc.value.translation_domain == "homeassistant"
    assert exc.value.translation_key == "service_not_found"
    assert exc.value.translation_placeholders == {
        "domain": "test_do_not",
        "service": "exist",
    }
    assert exc.value.domain == "test_do_not"
    assert exc.value.service == "exist"

    assert str(exc.value) == "Action test_do_not.exist not found"


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
    await hass.services.async_call("test_domain", "REGISTER_CALLS", blocking=False)
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
    await hass.services.async_call("test_domain", "REGISTER_CALLS", blocking=False)
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
    await async_setup_component(hass, "homeassistant", {})
    async_mock_service(hass, "test_domain", "test_service")
    with pytest.raises(ServiceValidationError, match="blocking=False") as exc:
        await hass.services.async_call(
            "test_domain",
            "test_service",
            service_data={},
            blocking=False,
            return_response=True,
        )
    assert str(exc.value) == (
        "A non blocking action call with argument blocking=False "
        "can't be used together with argument return_response=True"
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
    await async_setup_component(hass, "homeassistant", {})

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


@pytest.mark.parametrize(
    ("supports_response", "return_response", "expected_error"),
    [
        (SupportsResponse.NONE, True, "does not return responses"),
        (SupportsResponse.ONLY, False, "action requires responses"),
    ],
)
async def test_serviceregistry_return_response_arguments(
    hass: HomeAssistant,
    supports_response: SupportsResponse,
    return_response: bool,
    expected_error: str,
) -> None:
    """Test service call response data invalid arguments."""
    await async_setup_component(hass, "homeassistant", {})

    hass.services.async_register(
        "test_domain",
        "test_service",
        "service_handler",
        supports_response=supports_response,
    )

    with pytest.raises(ServiceValidationError, match=expected_error):
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


async def test_start_taking_too_long(caplog: pytest.LogCaptureFixture) -> None:
    """Test when async_start takes too long."""
    hass = ha.HomeAssistant("/test/ha-config")
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


def test_context_json_fragment() -> None:
    """Test context JSON fragments."""
    context1, context2 = (ha.Context(id="01H0D6K3RFJAYAV2093ZW30PCW") for _ in range(2))

    # We are testing that the JSON fragments are the same when as_dict is called
    # after json_fragment or before.
    json_fragment_1 = context1.json_fragment
    as_dict_1 = context1.as_dict()
    as_dict_2 = context2.as_dict()
    json_fragment_2 = context2.json_fragment

    assert json_dumps(json_fragment_1) == json_dumps(json_fragment_2)
    # We also test that the as_dict is the same
    assert as_dict_1 == as_dict_2

    # Finally we verify that the as_dict is a ReadOnlyDict
    # regardless of if the json fragment was called first or not
    assert isinstance(as_dict_1, ReadOnlyDict)
    assert isinstance(as_dict_2, ReadOnlyDict)


async def test_async_functions_with_callback(hass: HomeAssistant) -> None:
    """Test we deal with async functions accidentally marked as callback."""
    runs = []

    @ha.callback
    async def test():  # pylint: disable=hass-async-callback-decorator
        runs.append(True)

    await hass.async_add_job(test)
    assert len(runs) == 1

    hass.async_run_job(test)
    await hass.async_block_till_done()
    assert len(runs) == 2

    @ha.callback
    async def service_handler(call):  # pylint: disable=hass-async-callback-decorator
        runs.append(True)

    hass.services.async_register("test_domain", "test_service", service_handler)

    await hass.services.async_call("test_domain", "test_service", blocking=True)
    assert len(runs) == 3


async def test_async_run_job_starts_tasks_eagerly(hass: HomeAssistant) -> None:
    """Test async_run_job starts tasks eagerly."""
    runs = []

    async def _test():
        runs.append(True)

    task = hass.async_run_job(_test)
    # No call to hass.async_block_till_done to ensure the task is run eagerly
    assert len(runs) == 1
    assert task.done()
    await task


async def test_async_run_job_starts_coro_eagerly(hass: HomeAssistant) -> None:
    """Test async_run_job starts coros eagerly."""
    runs = []

    async def _test():
        runs.append(True)

    task = hass.async_run_job(_test())
    # No call to hass.async_block_till_done to ensure the task is run eagerly
    assert len(runs) == 1
    assert task.done()
    await task


def test_valid_entity_id() -> None:
    """Test valid entity ID."""
    for invalid in (
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
    ):
        assert not ha.valid_entity_id(invalid), invalid

    for valid in (
        "1.a",
        "1light.kitchen",
        "a.1",
        "a.a",
        "input_boolean.hello_world_0123",
        "light.1kitchen",
        "light.kitchen",
        "light.something_yoo",
    ):
        assert ha.valid_entity_id(valid), valid


def test_valid_domain() -> None:
    """Test valid domain."""
    for invalid in (
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
    ):
        assert not ha.valid_domain(invalid), invalid

    for valid in (
        "1",
        "1light",
        "a",
        "input_boolean",
        "light",
    ):
        assert ha.valid_domain(valid), valid


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

    hass.async_create_task(_wait_a_bit_1(), eager_start=False)
    await hass.async_block_till_done()

    with patch.object(ha, "BLOCK_LOG_TIMEOUT", 0.0001):
        hass.async_create_task(_wait_a_bit_2(), eager_start=False)
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
        hass.async_create_task(_task_chain_2(), eager_start=False)

    async def _task_chain_2():
        nonlocal created
        created += 1
        if created > 1000:
            return
        hass.async_create_task(_task_chain_1(), eager_start=False)

    with patch.object(ha, "BLOCK_LOG_TIMEOUT", 0.0):
        hass.async_create_task(_task_chain_1())
        await hass.async_block_till_done(wait_background_tasks=False)

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
        hass.async_create_task(_task_chain_2(), eager_start=False)

    async def _task_chain_2():
        nonlocal created
        created += 1
        if created > 10:
            return
        hass.async_create_task(_task_chain_1(), eager_start=False)

    hass.async_create_task(_task_chain_1(), eager_start=False)
    await hass.async_block_till_done()

    assert "_task_chain_" not in caplog.text


async def test_async_all(hass: HomeAssistant) -> None:
    """Test async_all."""
    assert hass.states.async_all() == []
    assert hass.states.async_all("light") == []
    assert hass.states.async_all(["light", "switch"]) == []

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

    assert hass.states.async_entity_ids_count() == 0
    assert hass.states.async_entity_ids_count("light") == 0
    assert hass.states.async_entity_ids_count({"light", "vacuum"}) == 0

    hass.states.async_set("switch.link", "on")
    hass.states.async_set("light.bowl", "on")
    hass.states.async_set("light.frog", "on")
    hass.states.async_set("vacuum.floor", "on")

    assert hass.states.async_entity_ids_count() == 4
    assert hass.states.async_entity_ids_count("light") == 2

    hass.states.async_set("light.cow", "on")

    assert hass.states.async_entity_ids_count() == 5
    assert hass.states.async_entity_ids_count("light") == 3
    assert hass.states.async_entity_ids_count({"light", "vacuum"}) == 4


async def test_hassjob_forbid_coroutine() -> None:
    """Test hassjob forbids coroutines."""

    async def bla():
        pass

    coro = bla()

    with pytest.raises(ValueError):
        _ = ha.HassJob(coro).job_type

    # To avoid warning about unawaited coro
    await coro


async def test_reserving_states(hass: HomeAssistant) -> None:
    """Test we can reserve a state in the state machine."""

    hass.states.async_reserve("light.bedroom")
    assert hass.states.async_available("light.bedroom") is False
    hass.states.async_set("light.bedroom", "on")
    assert hass.states.async_available("light.bedroom") is False

    with pytest.raises(HomeAssistantError):
        hass.states.async_reserve("light.bedroom")

    hass.states.async_remove("light.bedroom")
    assert hass.states.async_available("light.bedroom") is True
    hass.states.async_set("light.bedroom", "on")

    with pytest.raises(HomeAssistantError):
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
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    hass.states.async_set("light.bedroom", "on")
    await hass.async_block_till_done()
    state: State = hass.states.get("light.bedroom")
    assert state.last_updated == events[0].time_fired
    assert len(state.context.id) == 26
    # ULIDs store time to 3 decimal places compared to python timestamps
    assert _ulid_timestamp(state.context.id) == int(state.last_updated_timestamp * 1000)


async def test_state_change_events_match_time_with_limits_of_precision(
    hass: HomeAssistant,
) -> None:
    """Ensure last_updated matches last_updated_timestamp within limits of precision.

    The last_updated_timestamp uses the same precision as time.time() which is
    a bit better than the precision of datetime.now() which is used for last_updated
    on some platforms.
    """
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    hass.states.async_set("light.bedroom", "on")
    await hass.async_block_till_done()
    state: State = hass.states.get("light.bedroom")
    assert state.last_updated == events[0].time_fired
    assert state.last_updated_timestamp == pytest.approx(
        events[0].time_fired.timestamp()
    )
    assert state.last_updated_timestamp == pytest.approx(state.last_updated.timestamp())
    assert state.last_updated_timestamp == state.last_changed_timestamp
    assert state.last_updated_timestamp == pytest.approx(state.last_changed.timestamp())
    assert state.last_updated_timestamp == state.last_reported_timestamp
    assert state.last_updated_timestamp == pytest.approx(
        state.last_reported.timestamp()
    )


def test_state_timestamps() -> None:
    """Test timestamp functions for State."""
    now = dt_util.utcnow()
    state = ha.State(
        "light.bedroom",
        "on",
        {"brightness": 100},
        last_changed=now,
        last_reported=now,
        last_updated=now,
        context=ha.Context(id="1234"),
    )
    assert state.last_changed_timestamp == now.timestamp()
    assert state.last_changed_timestamp == now.timestamp()
    assert state.last_reported_timestamp == now.timestamp()
    assert state.last_reported_timestamp == now.timestamp()
    assert state.last_updated_timestamp == now.timestamp()
    assert state.last_updated_timestamp == now.timestamp()


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


@pytest.mark.parametrize("eager_start", [True, False])
async def test_background_task(hass: HomeAssistant, eager_start: bool) -> None:
    """Test background tasks being quit."""
    result = asyncio.Future()

    async def test_task():
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            result.set_result(hass.state)
            raise

    task = hass.async_create_background_task(
        test_task(), "happy task", eager_start=eager_start
    )
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


@pytest.mark.parametrize("eager_start", [True, False])
async def test_cancellable_hassjob(hass: HomeAssistant, eager_start: bool) -> None:
    """Simulate a shutdown, ensure cancellable jobs are cancelled."""
    job = MagicMock()

    @ha.callback
    def run_job(job: HassJob) -> None:
        """Call the action."""
        hass.async_run_hass_job(job, eager_start=True)

    timer1 = hass.loop.call_later(
        60, run_job, HassJob(ha.callback(job), cancel_on_shutdown=True)
    )
    timer2 = hass.loop.call_later(60, run_job, HassJob(ha.callback(job)))

    await hass.async_stop()

    assert timer1.cancelled()
    assert not timer2.cancelled()

    # Cleanup
    timer2.cancel()


async def test_validate_state(hass: HomeAssistant) -> None:
    """Test validate_state."""
    assert ha.validate_state("test") == "test"
    with pytest.raises(InvalidStateError):
        ha.validate_state("t" * 256)


@pytest.mark.parametrize(
    ("version", "release_channel"),
    [
        ("0.115.0.dev20200815", ReleaseChannel.NIGHTLY),
        ("0.115.0", ReleaseChannel.STABLE),
        ("0.115.0b4", ReleaseChannel.BETA),
        ("0.115.0dev0", ReleaseChannel.DEV),
    ],
)
async def test_get_release_channel(
    version: str, release_channel: ReleaseChannel
) -> None:
    """Test if release channel detection works from Home Assistant version number."""
    with patch("homeassistant.core.__version__", f"{version}"):
        assert get_release_channel() == release_channel


def test_is_callback_check_partial() -> None:
    """Test is_callback_check_partial matches HassJob."""

    @ha.callback
    def callback_func() -> None:
        pass

    def not_callback_func() -> None:
        pass

    assert ha.is_callback(callback_func)
    assert HassJob(callback_func).job_type == ha.HassJobType.Callback
    assert ha.is_callback_check_partial(functools.partial(callback_func))
    assert HassJob(functools.partial(callback_func)).job_type == ha.HassJobType.Callback
    assert ha.is_callback_check_partial(
        functools.partial(functools.partial(callback_func))
    )
    assert HassJob(functools.partial(functools.partial(callback_func))).job_type == (
        ha.HassJobType.Callback
    )
    assert not ha.is_callback_check_partial(not_callback_func)
    assert HassJob(not_callback_func).job_type == ha.HassJobType.Executor
    assert not ha.is_callback_check_partial(functools.partial(not_callback_func))
    assert HassJob(functools.partial(not_callback_func)).job_type == (
        ha.HassJobType.Executor
    )

    # We check the inner function, not the outer one
    assert not ha.is_callback_check_partial(
        ha.callback(functools.partial(not_callback_func))
    )
    assert HassJob(ha.callback(functools.partial(not_callback_func))).job_type == (
        ha.HassJobType.Executor
    )


def test_hassjob_passing_job_type() -> None:
    """Test passing the job type to HassJob when we already know it."""

    @ha.callback
    def callback_func() -> None:
        pass

    def not_callback_func() -> None:
        pass

    assert (
        HassJob(callback_func, job_type=ha.HassJobType.Callback).job_type
        == ha.HassJobType.Callback
    )

    # We should trust the job_type passed in
    assert (
        HassJob(not_callback_func, job_type=ha.HassJobType.Callback).job_type
        == ha.HassJobType.Callback
    )


async def test_shutdown_job(hass: HomeAssistant) -> None:
    """Test async_add_shutdown_job."""
    evt = asyncio.Event()

    async def shutdown_func() -> None:
        # Sleep to ensure core is waiting for the task to finish
        await asyncio.sleep(0.01)
        # Set the event
        evt.set()

    job = HassJob(shutdown_func, "shutdown_job")
    hass.async_add_shutdown_job(job)
    await hass.async_stop()
    assert evt.is_set()


async def test_cancel_shutdown_job(hass: HomeAssistant) -> None:
    """Test cancelling a job added to async_add_shutdown_job."""
    evt = asyncio.Event()

    async def shutdown_func() -> None:
        evt.set()

    job = HassJob(shutdown_func, "shutdown_job")
    cancel = hass.async_add_shutdown_job(job)
    cancel()
    await hass.async_stop()
    assert not evt.is_set()


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(ha)


def test_deprecated_config(caplog: pytest.LogCaptureFixture) -> None:
    """Test deprecated Config class."""
    import_and_test_deprecated_alias(caplog, ha, "Config", Config, "2025.11")


def test_one_time_listener_repr(hass: HomeAssistant) -> None:
    """Test one time listener repr."""

    def _listener(event: ha.Event):
        """Test listener."""

    one_time_listener = ha._OneTimeListener(hass, HassJob(_listener))
    repr_str = repr(one_time_listener)
    assert "OneTimeListener" in repr_str
    assert "test_core" in repr_str
    assert "_listener" in repr_str


async def test_async_add_import_executor_job(hass: HomeAssistant) -> None:
    """Test async_add_import_executor_job works and is limited to one thread."""
    evt = threading.Event()
    loop = asyncio.get_running_loop()

    def executor_func() -> threading.Event:
        evt.set()
        return evt

    future = hass.async_add_import_executor_job(executor_func)
    await loop.run_in_executor(None, evt.wait)
    assert await future is evt

    assert hass.import_executor._max_workers == 1


async def test_async_run_job_deprecated(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test async_run_job warns about its deprecation."""

    async def _test() -> None:
        pass

    hass.async_run_job(_test)
    assert (
        "Detected code that calls `async_run_job`, which should be reviewed against "
        "https://developers.home-assistant.io/blog/2024/03/13/deprecate_add_run_job"
        " for replacement options. This will stop working in Home Assistant 2025.4"
    ) in caplog.text


async def test_async_add_job_deprecated(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test async_add_job warns about its deprecation."""

    async def _test() -> None:
        pass

    hass.async_add_job(_test)
    assert (
        "Detected code that calls `async_add_job`, which should be reviewed against "
        "https://developers.home-assistant.io/blog/2024/03/13/deprecate_add_run_job"
        " for replacement options. This will stop working in Home Assistant 2025.4"
    ) in caplog.text


async def test_async_add_hass_job_deprecated(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test async_add_hass_job warns about its deprecation."""

    async def _test() -> None:
        pass

    hass.async_add_hass_job(HassJob(_test))
    assert (
        "Detected code that calls `async_add_hass_job`, which should be reviewed against "
        "https://developers.home-assistant.io/blog/2024/04/07/deprecate_add_hass_job"
        " for replacement options. This will stop working in Home Assistant 2025.5"
    ) in caplog.text


async def test_eventbus_lazy_object_creation(hass: HomeAssistant) -> None:
    """Test we don't create unneeded objects when firing events."""
    calls = []

    @ha.callback
    def listener(event):
        """Mock listener."""
        calls.append(event)

    @ha.callback
    def mock_filter(event_data):
        """Mock filter."""
        return not event_data["filtered"]

    unsub = hass.bus.async_listen("test_1", listener, event_filter=mock_filter)

    # Test lazy creation of Event objects
    with patch("homeassistant.core.Event") as mock_event:
        # Fire an event which is filtered out by its listener
        hass.bus.async_fire("test_1", {"filtered": True})
        await hass.async_block_till_done()
        mock_event.assert_not_called()
        assert len(calls) == 0

        # Fire an event which has no listener
        hass.bus.async_fire("test_2")
        await hass.async_block_till_done()
        mock_event.assert_not_called()
        assert len(calls) == 0

        # Fire an event which is not filtered out by its listener
        hass.bus.async_fire("test_1", {"filtered": False})
        await hass.async_block_till_done()
        mock_event.assert_called_once()
        assert len(calls) == 1

    calls = []
    # Test lazy creation of Context objects
    with patch("homeassistant.core.Context") as mock_context:
        # Fire an event which is filtered out by its listener
        hass.bus.async_fire("test_1", {"filtered": True})
        await hass.async_block_till_done()
        mock_context.assert_not_called()
        assert len(calls) == 0

        # Fire an event which has no listener
        hass.bus.async_fire("test_2")
        await hass.async_block_till_done()
        mock_context.assert_not_called()
        assert len(calls) == 0

        # Fire an event which is not filtered out by its listener
        hass.bus.async_fire("test_1", {"filtered": False})
        await hass.async_block_till_done()
        mock_context.assert_called_once()
        assert len(calls) == 1

    unsub()


async def test_event_filter_sanity_checks(hass: HomeAssistant) -> None:
    """Test raising on bad event filters."""

    @ha.callback
    def listener(event):
        """Mock listener."""

    def bad_filter(event_data):
        """Mock filter."""
        return False

    with pytest.raises(HomeAssistantError):
        hass.bus.async_listen("test", listener, event_filter=bad_filter)


async def test_statemachine_report_state(hass: HomeAssistant) -> None:
    """Test report state event."""

    @ha.callback
    def mock_filter(event_data):
        """Mock filter."""
        return True

    @callback
    def listener(event: ha.Event) -> None:
        state_reported_events.append(event)

    hass.states.async_set("light.bowl", "on", {})
    state_changed_events = async_capture_events(hass, EVENT_STATE_CHANGED)
    state_reported_events = []
    unsub = hass.bus.async_listen(
        EVENT_STATE_REPORTED, listener, event_filter=mock_filter
    )

    hass.states.async_set("light.bowl", "on")
    await hass.async_block_till_done()
    assert len(state_changed_events) == 0
    assert len(state_reported_events) == 1

    hass.states.async_set("light.bowl", "on", None, True)
    await hass.async_block_till_done()
    assert len(state_changed_events) == 1
    assert len(state_reported_events) == 1

    hass.states.async_set("light.bowl", "off")
    await hass.async_block_till_done()
    assert len(state_changed_events) == 2
    assert len(state_reported_events) == 1

    hass.states.async_remove("light.bowl")
    await hass.async_block_till_done()
    assert len(state_changed_events) == 3
    assert len(state_reported_events) == 1

    unsub()

    hass.states.async_set("light.bowl", "on")
    await hass.async_block_till_done()
    assert len(state_changed_events) == 4
    assert len(state_reported_events) == 1


async def test_report_state_listener_restrictions(hass: HomeAssistant) -> None:
    """Test we enforce requirements for EVENT_STATE_REPORTED listeners."""

    @ha.callback
    def listener(event):
        """Mock listener."""

    @ha.callback
    def mock_filter(event_data):
        """Mock filter."""
        return False

    # no filter
    with pytest.raises(HomeAssistantError):
        hass.bus.async_listen(EVENT_STATE_REPORTED, listener)

    # Both filter and run_immediately
    hass.bus.async_listen(EVENT_STATE_REPORTED, listener, event_filter=mock_filter)


@pytest.mark.parametrize(
    "run_immediately",
    [True, False],
)
@pytest.mark.parametrize(
    "method",
    ["async_listen", "async_listen_once"],
)
async def test_async_listen_with_run_immediately_deprecated(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    run_immediately: bool,
    method: str,
) -> None:
    """Test async_add_job warns about its deprecation."""

    async def _test(event: ha.Event):
        pass

    func = getattr(hass.bus, method)
    func(EVENT_HOMEASSISTANT_START, _test, run_immediately=run_immediately)
    assert (
        f"Detected code that calls `{method}` with run_immediately. "
        "This will stop working in Home Assistant 2025.5"
    ) in caplog.text


async def test_async_fire_thread_safety(hass: HomeAssistant) -> None:
    """Test async_fire thread safety."""
    events = async_capture_events(hass, "test_event")
    hass.bus.async_fire("test_event")
    with pytest.raises(
        RuntimeError,
        match="Detected code that calls hass.bus.async_fire from a thread.",
    ):
        await hass.async_add_executor_job(hass.bus.async_fire, "test_event")

    assert len(events) == 1


async def test_async_register_thread_safety(hass: HomeAssistant) -> None:
    """Test async_register thread safety."""
    with pytest.raises(
        RuntimeError,
        match="Detected code that calls hass.services.async_register from a thread.",
    ):
        await hass.async_add_executor_job(
            hass.services.async_register,
            "test_domain",
            "test_service",
            lambda call: None,
        )


async def test_async_remove_thread_safety(hass: HomeAssistant) -> None:
    """Test async_remove thread safety."""
    with pytest.raises(
        RuntimeError,
        match="Detected code that calls hass.services.async_remove from a thread.",
    ):
        await hass.async_add_executor_job(
            hass.services.async_remove, "test_domain", "test_service"
        )


async def test_async_create_task_thread_safety(hass: HomeAssistant) -> None:
    """Test async_create_task thread safety."""

    async def _any_coro():
        pass

    with pytest.raises(
        RuntimeError,
        match="Detected code that calls hass.async_create_task from a thread.",
    ):
        await hass.async_add_executor_job(hass.async_create_task, _any_coro)


async def test_thread_safety_message(hass: HomeAssistant) -> None:
    """Test the thread safety message."""
    with pytest.raises(
        RuntimeError,
        match=re.escape(
            "Detected code that calls test from a thread other than the event loop, "
            "which may cause Home Assistant to crash or data to corrupt. For more "
            "information, see "
            "https://developers.home-assistant.io/docs/asyncio_thread_safety/#test"
            ". Please report this issue",
        ),
    ):
        await hass.async_add_executor_job(hass.verify_event_loop_thread, "test")


async def test_async_set_updates_last_reported(hass: HomeAssistant) -> None:
    """Test async_set method updates last_reported AND last_reported_timestamp."""
    hass.states.async_set("light.bowl", "on", {})
    state = hass.states.get("light.bowl")
    last_reported = state.last_reported
    last_reported_timestamp = state.last_reported_timestamp

    for _ in range(2):
        hass.states.async_set("light.bowl", "on", {})
        assert state.last_reported != last_reported
        assert state.last_reported_timestamp != last_reported_timestamp
        last_reported = state.last_reported
        last_reported_timestamp = state.last_reported_timestamp
