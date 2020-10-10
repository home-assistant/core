"""Test Home Assistant thread utils."""

import asyncio

import pytest

from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.thread import ThreadWithException


async def test_thread_with_exception_invalid(hass):
    """Test throwing an invalid thread exception."""

    finish_event = asyncio.Event()

    def _do_nothing(*_):
        run_callback_threadsafe(hass.loop, finish_event.set)

    test_thread = ThreadWithException(target=_do_nothing)
    test_thread.start()
    await asyncio.wait_for(finish_event.wait(), timeout=0.1)

    with pytest.raises(TypeError):
        test_thread.raise_exc(_EmptyClass())
    test_thread.join()


async def test_thread_not_started(hass):
    """Test throwing when the thread is not started."""

    test_thread = ThreadWithException(target=lambda *_: None)

    with pytest.raises(AssertionError):
        test_thread.raise_exc(TimeoutError)


async def test_thread_fails_raise(hass):
    """Test throwing after already ended."""

    finish_event = asyncio.Event()

    def _do_nothing(*_):
        run_callback_threadsafe(hass.loop, finish_event.set)

    test_thread = ThreadWithException(target=_do_nothing)
    test_thread.start()
    await asyncio.wait_for(finish_event.wait(), timeout=0.1)
    test_thread.join()

    with pytest.raises(SystemError):
        test_thread.raise_exc(ValueError)


class _EmptyClass:
    """An empty class."""
