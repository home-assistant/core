"""Tests for debounce."""
import asyncio
from datetime import timedelta
import logging
from unittest.mock import AsyncMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import debounce
from homeassistant.util.dt import utcnow

from ..common import async_fire_time_changed

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

    # Test calling doesn't execute/cooldown if currently executing.
    await debouncer._execute_lock.acquire()
    await debouncer.async_call()
    assert len(calls) == 2
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    debouncer._execute_lock.release()
    assert debouncer._job.target == debouncer.function


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

    # Test calling doesn't schedule if currently executing.
    await debouncer._execute_lock.acquire()
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    debouncer._execute_lock.release()
    assert debouncer._job.target == debouncer.function


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

    # Test calling doesn't execute/cooldown if currently executing.
    await debouncer._execute_lock.acquire()
    await debouncer.async_call()
    assert len(calls) == 2
    assert calls == [1, 2]
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    debouncer._execute_lock.release()
    assert debouncer._job.target == debouncer.function


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
    await debouncer.async_shutdown()
    future.set_result(True)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert debouncer._timer_task is None

    assert "Debouncer call ignored as shutdown has been requested." not in caplog.text
    await debouncer.async_call()
    assert "Debouncer call ignored as shutdown has been requested." in caplog.text

    assert len(calls) == 1
    assert debouncer._timer_task is None
