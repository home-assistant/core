"""Tests for debounce."""
from homeassistant.helpers import debounce

from tests.async_mock import AsyncMock


async def test_immediate_works(hass):
    """Test immediate works."""
    calls = []
    debouncer = debounce.Debouncer(
        hass,
        None,
        cooldown=0.01,
        immediate=True,
        function=AsyncMock(side_effect=lambda: calls.append(None)),
    )

    # Call when nothing happening
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is False

    # Call when cooldown active setting execute at end to True
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True

    # Canceling debounce in cooldown
    debouncer.async_cancel()
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False

    # Call and let timer run out
    await debouncer.async_call()
    assert len(calls) == 2
    await debouncer._handle_timer_finish()
    assert len(calls) == 2
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False

    # Test calling doesn't execute/cooldown if currently executing.
    await debouncer._execute_lock.acquire()
    await debouncer.async_call()
    assert len(calls) == 2
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    debouncer._execute_lock.release()


async def test_not_immediate_works(hass):
    """Test immediate works."""
    calls = []
    debouncer = debounce.Debouncer(
        hass,
        None,
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
    await debouncer._handle_timer_finish()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is False

    # Reset debouncer
    debouncer.async_cancel()

    # Test calling doesn't schedule if currently executing.
    await debouncer._execute_lock.acquire()
    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
    debouncer._execute_lock.release()
