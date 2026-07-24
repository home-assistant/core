"""Tests for debounce."""

import asyncio
from datetime import timedelta
import logging
from unittest.mock import AsyncMock, Mock
import weakref

import pytest

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import debounce
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_immediate_works(hass: HomeAssistant) -> None:
    """Test immediate works."""
    calls = []
    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=0.01,
        immediate=True,
        function=AsyncMock(side_effect=lambda: calls.append(None)),
    )

    # Call when nothing happening
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    # Call when cooldown active setting execute at end to True
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True
    assert debouncer._job.target == debouncer.function

    # Canceling debounce in cooldown
    debouncer.async_cancel()
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    before_job = debouncer._job

    # Call and let timer run out
    await debouncer.async_call()
    assert len(calls) == 2
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function
    assert debouncer._job == before_job

    # Test calling enabled timer if currently executing.
    await debouncer._execute_lock.acquire()
    await debouncer.async_call()
    assert len(calls) == 2
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True
    debouncer._execute_lock.release()
    assert debouncer._job.target == debouncer.function

    debouncer.async_shutdown()


async def test_immediate_works_with_schedule_call(hass: HomeAssistant) -> None:
    """Test immediate works with scheduled calls."""
    calls = []
    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=0.01,
        immediate=True,
        function=AsyncMock(side_effect=lambda: calls.append(None)),
    )

    # Call when nothing happening
    debouncer.async_schedule_call()
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    # Call when cooldown active setting execute at end to True
    debouncer.async_schedule_call()
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True
    assert debouncer._job.target == debouncer.function

    # Canceling debounce in cooldown
    debouncer.async_cancel()
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    before_job = debouncer._job

    # Call and let timer run out
    debouncer.async_schedule_call()
    await hass.async_block_till_done()
    assert len(calls) == 2
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function
    assert debouncer._job == before_job

    # Test calling enabled timer if currently executing.
    await debouncer._execute_lock.acquire()
    debouncer.async_schedule_call()
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True
    debouncer._execute_lock.release()
    assert debouncer._job.target == debouncer.function

    debouncer.async_shutdown()


async def test_immediate_works_with_callback_function(hass: HomeAssistant) -> None:
    """Test immediate works with callback function."""
    calls = []
    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=0.01,
        immediate=True,
        function=callback(Mock(side_effect=lambda: calls.append(None))),
    )

    # Call when nothing happening
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    debouncer.async_shutdown()


async def test_immediate_works_with_executor_function(hass: HomeAssistant) -> None:
    """Test immediate works with executor function."""
    calls = []
    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=0.01,
        immediate=True,
        function=Mock(side_effect=lambda: calls.append(None)),
    )

    # Call when nothing happening
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    debouncer.async_shutdown()


async def test_immediate_works_with_passed_callback_function_raises(
    hass: HomeAssistant,
) -> None:
    """Test immediate works with a callback function that raises."""
    calls = []

    @callback
    def _append_and_raise() -> None:
        calls.append(None)
        raise RuntimeError("forced_raise")

    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=0.01,
        immediate=True,
        function=_append_and_raise,
    )

    # Call when nothing happening
    with pytest.raises(RuntimeError, match="forced_raise"):
        await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    # Call when cooldown active setting execute at end to True
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True
    assert debouncer._job.target == debouncer.function

    # Canceling debounce in cooldown
    debouncer.async_cancel()
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    before_job = debouncer._job

    # Call and let timer run out
    with pytest.raises(RuntimeError, match="forced_raise"):
        await debouncer.async_call()
    assert len(calls) == 2
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function
    assert debouncer._job == before_job

    # Test calling enabled timer if currently executing.
    await debouncer._execute_lock.acquire()
    await debouncer.async_call()
    assert len(calls) == 2
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True
    debouncer._execute_lock.release()
    assert debouncer._job.target == debouncer.function

    debouncer.async_shutdown()


async def test_immediate_works_with_passed_coroutine_raises(
    hass: HomeAssistant,
) -> None:
    """Test immediate works with a coroutine that raises."""
    calls = []

    async def _append_and_raise() -> None:
        calls.append(None)
        raise RuntimeError("forced_raise")

    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=0.01,
        immediate=True,
        function=_append_and_raise,
    )

    # Call when nothing happening
    with pytest.raises(RuntimeError, match="forced_raise"):
        await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    # Call when cooldown active setting execute at end to True
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True
    assert debouncer._job.target == debouncer.function

    # Canceling debounce in cooldown
    debouncer.async_cancel()
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    before_job = debouncer._job

    # Call and let timer run out
    with pytest.raises(RuntimeError, match="forced_raise"):
        await debouncer.async_call()
    assert len(calls) == 2
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function
    assert debouncer._job == before_job

    # Test calling enabled timer if currently executing.
    await debouncer._execute_lock.acquire()
    await debouncer.async_call()
    assert len(calls) == 2
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True
    debouncer._execute_lock.release()
    assert debouncer._job.target == debouncer.function

    debouncer.async_shutdown()


async def test_not_immediate_works(hass: HomeAssistant) -> None:
    """Test immediate works."""
    calls = []
    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=0.01,
        immediate=False,
        function=AsyncMock(side_effect=lambda: calls.append(None)),
    )

    # Call when nothing happening
    await debouncer.async_call()
    assert len(calls) == 0
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True

    # Call while still on cooldown
    await debouncer.async_call()
    assert len(calls) == 0
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True

    # Canceling while on cooldown
    debouncer.async_cancel()
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False

    # Call and let timer run out
    await debouncer.async_call()
    assert len(calls) == 0
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    # Reset debouncer
    debouncer.async_cancel()

    # Test calling enabled timer if currently executing.
    await debouncer._execute_lock.acquire()
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True
    debouncer._execute_lock.release()
    assert debouncer._job.target == debouncer.function

    debouncer.async_shutdown()


async def test_not_immediate_works_schedule_call(hass: HomeAssistant) -> None:
    """Test immediate works with schedule call."""
    calls = []
    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=0.01,
        immediate=False,
        function=AsyncMock(side_effect=lambda: calls.append(None)),
    )

    # Call when nothing happening
    debouncer.async_schedule_call()
    await hass.async_block_till_done()
    assert len(calls) == 0
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True

    # Call while still on cooldown
    debouncer.async_schedule_call()
    await hass.async_block_till_done()
    assert len(calls) == 0
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True

    # Canceling while on cooldown
    debouncer.async_cancel()
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False

    # Call and let timer run out
    debouncer.async_schedule_call()
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    # Reset debouncer
    debouncer.async_cancel()

    # Test calling enabled timer if currently executing.
    await debouncer._execute_lock.acquire()
    debouncer.async_schedule_call()
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True
    debouncer._execute_lock.release()
    assert debouncer._job.target == debouncer.function

    debouncer.async_shutdown()


async def test_immediate_works_with_function_swapped(hass: HomeAssistant) -> None:
    """Test immediate works and we can change out the function."""
    calls = []

    one_function = AsyncMock(side_effect=lambda: calls.append(1))
    two_function = AsyncMock(side_effect=lambda: calls.append(2))

    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=0.01,
        immediate=True,
        function=one_function,
    )

    # Call when nothing happening
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    # Call when cooldown active setting execute at end to True
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True
    assert debouncer._job.target == debouncer.function

    # Canceling debounce in cooldown
    debouncer.async_cancel()
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function

    before_job = debouncer._job
    debouncer.function = two_function

    # Call and let timer run out
    await debouncer.async_call()
    assert len(calls) == 2
    assert calls == [1, 2]
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls == [1, 2]
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    assert debouncer._job.target == debouncer.function
    assert debouncer._job != before_job

    # Test calling enabled timer if currently executing.
    await debouncer._execute_lock.acquire()
    await debouncer.async_call()
    assert len(calls) == 2
    assert calls == [1, 2]
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True
    debouncer._execute_lock.release()
    assert debouncer._job.target == debouncer.function

    debouncer.async_shutdown()


async def test_shutdown(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test shutdown."""
    calls = []
    future = asyncio.Future()

    async def _func() -> None:
        await future
        calls.append(None)

    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=0.01,
        immediate=False,
        function=_func,
    )

    # Ensure shutdown during a run doesn't create a cooldown timer
    hass.async_create_task(debouncer.async_call())
    await asyncio.sleep(0.01)
    debouncer.async_shutdown()
    future.set_result(True)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert debouncer._timer_task is None

    assert "Debouncer call ignored as shutdown has been requested." not in caplog.text
    await debouncer.async_call()
    assert "Debouncer call ignored as shutdown has been requested." in caplog.text

    assert len(calls) == 1
    assert debouncer._timer_task is None


async def test_background(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test background tasks are created when background is True."""
    calls = []

    async def _func() -> None:
        await asyncio.sleep(0.1)
        calls.append(None)

    debouncer = debounce.Debouncer(
        hass, _LOGGER, cooldown=0.05, immediate=True, function=_func, background=True
    )

    await debouncer.async_call()
    assert len(calls) == 1

    debouncer.async_schedule_call()
    assert len(calls) == 1

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done(wait_background_tasks=False)
    assert len(calls) == 1

    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(calls) == 2

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done(wait_background_tasks=False)
    assert len(calls) == 2


async def test_shutdown_releases_parent_class(hass: HomeAssistant) -> None:
    """Test shutdown releases parent class.

    See https://github.com/home-assistant/core/issues/137237
    """
    calls = []

    class SomeClass:
        def run_func(self) -> None:
            calls.append(None)

    my_class = SomeClass()
    my_class_weak_ref = weakref.ref(my_class)

    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=0.01,
        immediate=True,
        function=my_class.run_func,
    )

    # Debouncer keeps a reference to the function, prevening GC
    del my_class
    await debouncer.async_call()
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert my_class_weak_ref() is not None

    # Debouncer shutdown releases the class
    debouncer.async_shutdown()
    assert my_class_weak_ref() is None


async def test_schedule_timer_cancels_previous_handle(hass: HomeAssistant) -> None:
    """Ensure _schedule_timer cancels any previously-scheduled handle."""
    # Use a large cooldown so the scheduled timer can't fire mid-test on a slow
    # event loop; the timer is only inspected and cancelled, never awaited.
    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=3600.0,
        immediate=True,
        function=AsyncMock(),
    )

    debouncer._schedule_timer()
    first_handle = debouncer._timer_task
    assert first_handle is not None
    assert not first_handle.cancelled()

    debouncer._schedule_timer()
    second_handle = debouncer._timer_task
    assert second_handle is not None
    assert second_handle is not first_handle
    assert first_handle.cancelled()

    debouncer.async_shutdown()


async def test_concurrent_async_call_does_not_orphan_timer(
    hass: HomeAssistant,
) -> None:
    """Concurrent async_call during in-flight execution must not orphan a timer."""
    started = asyncio.Event()
    can_finish = asyncio.Event()

    async def slow_function() -> None:
        started.set()
        await can_finish.wait()

    # Use a large cooldown so the T1 timer scheduled below can't fire before
    # the in-flight call completes; cancellation is verified deterministically.
    debouncer = debounce.Debouncer(
        hass,
        _LOGGER,
        cooldown=3600.0,
        immediate=True,
        function=slow_function,
    )

    in_flight = hass.async_create_task(debouncer.async_call())
    await started.wait()
    assert debouncer._timer_task is None

    # The concurrent call hits the locked-immediate branch and schedules T1.
    await debouncer.async_call()
    first_timer = debouncer._timer_task
    assert first_timer is not None
    assert not first_timer.cancelled()

    # Letting the in-flight call complete schedules T2.
    can_finish.set()
    await in_flight
    second_timer = debouncer._timer_task
    assert second_timer is not None
    assert second_timer is not first_timer
    assert first_timer.cancelled()

    debouncer.async_shutdown()
