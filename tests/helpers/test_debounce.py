"""Tests for debounce."""
from asynctest import CoroutineMock

from homeassistant.helpers import debounce


async def test_immediate_works(hass):
    """Test immediate works."""
    calls = []
    debouncer = debounce.Debouncer(
        hass,
        None,
        cooldown=0.01,
        immediate=True,
        function=CoroutineMock(side_effect=lambda: calls.append(None)),
    )

    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is False

    await debouncer.async_call()
    assert len(calls) == 1
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True

    debouncer.async_cancel()
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False

    await debouncer.async_call()
    assert len(calls) == 2
    await debouncer._handle_timer_finish()
    assert len(calls) == 2
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False


async def test_not_immediate_works(hass):
    """Test immediate works."""
    calls = []
    debouncer = debounce.Debouncer(
        hass,
        None,
        cooldown=0.01,
        immediate=False,
        function=CoroutineMock(side_effect=lambda: calls.append(None)),
    )

    await debouncer.async_call()
    assert len(calls) == 0
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True

    await debouncer.async_call()
    assert len(calls) == 0
    assert debouncer._timer_task is not None
    assert debouncer._execute_at_end_of_timer is True

    debouncer.async_cancel()
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False

    await debouncer.async_call()
    assert len(calls) == 0
    await debouncer._handle_timer_finish()
    assert len(calls) == 1
    assert debouncer._timer_task is None
    assert debouncer._execute_at_end_of_timer is False
