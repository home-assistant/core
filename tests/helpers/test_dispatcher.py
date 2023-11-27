"""Test dispatcher helpers."""
from functools import partial

import pytest

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)


async def test_simple_function(hass: HomeAssistant) -> None:
    """Test simple function (executor)."""
    calls = []

    def test_funct(data):
        """Test function."""
        calls.append(data)

    async_dispatcher_connect(hass, "test", test_funct)
    async_dispatcher_send(hass, "test", 3)
    await hass.async_block_till_done()

    assert calls == [3]

    async_dispatcher_send(hass, "test", "bla")
    await hass.async_block_till_done()

    assert calls == [3, "bla"]


async def test_simple_function_unsub(hass: HomeAssistant) -> None:
    """Test simple function (executor) and unsub."""
    calls1 = []
    calls2 = []

    def test_funct1(data):
        """Test function."""
        calls1.append(data)

    def test_funct2(data):
        """Test function."""
        calls2.append(data)

    async_dispatcher_connect(hass, "test1", test_funct1)
    unsub = async_dispatcher_connect(hass, "test2", test_funct2)
    async_dispatcher_send(hass, "test1", 3)
    async_dispatcher_send(hass, "test2", 4)
    await hass.async_block_till_done()

    assert calls1 == [3]
    assert calls2 == [4]

    unsub()

    async_dispatcher_send(hass, "test1", 5)
    async_dispatcher_send(hass, "test2", 6)
    await hass.async_block_till_done()

    assert calls1 == [3, 5]
    assert calls2 == [4]

    # check don't kill the flow
    unsub()

    async_dispatcher_send(hass, "test1", 7)
    async_dispatcher_send(hass, "test2", 8)
    await hass.async_block_till_done()

    assert calls1 == [3, 5, 7]
    assert calls2 == [4]


async def test_simple_callback(hass: HomeAssistant) -> None:
    """Test simple callback (async)."""
    calls = []

    @callback
    def test_funct(data):
        """Test function."""
        calls.append(data)

    async_dispatcher_connect(hass, "test", test_funct)
    async_dispatcher_send(hass, "test", 3)
    await hass.async_block_till_done()

    assert calls == [3]

    async_dispatcher_send(hass, "test", "bla")
    await hass.async_block_till_done()

    assert calls == [3, "bla"]


async def test_simple_coro(hass: HomeAssistant) -> None:
    """Test simple coro (async)."""
    calls = []

    async def async_test_funct(data):
        """Test function."""
        calls.append(data)

    async_dispatcher_connect(hass, "test", async_test_funct)
    async_dispatcher_send(hass, "test", 3)
    await hass.async_block_till_done()

    assert calls == [3]

    async_dispatcher_send(hass, "test", "bla")
    await hass.async_block_till_done()

    assert calls == [3, "bla"]


async def test_simple_function_multiargs(hass: HomeAssistant) -> None:
    """Test simple function (executor)."""
    calls = []

    def test_funct(data1, data2, data3):
        """Test function."""
        calls.append(data1)
        calls.append(data2)
        calls.append(data3)

    async_dispatcher_connect(hass, "test", test_funct)
    async_dispatcher_send(hass, "test", 3, 2, "bla")
    await hass.async_block_till_done()

    assert calls == [3, 2, "bla"]


@pytest.mark.no_fail_on_log_exception
async def test_callback_exception_gets_logged(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test exception raised by signal handler."""

    @callback
    def bad_handler(*args):
        """Record calls."""
        raise Exception("This is a bad message callback")

    # wrap in partial to test message logging.
    async_dispatcher_connect(hass, "test", partial(bad_handler))
    async_dispatcher_send(hass, "test", "bad")
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert (
        f"Exception in functools.partial({bad_handler}) when dispatching 'test': ('bad',)"
        in caplog.text
    )


async def test_dispatcher_add_dispatcher(hass: HomeAssistant) -> None:
    """Test adding a dispatcher from a dispatcher."""
    calls = []

    @callback
    def _new_dispatcher(data):
        calls.append(data)

    @callback
    def _add_new_dispatcher(data):
        calls.append(data)
        async_dispatcher_connect(hass, "test", _new_dispatcher)

    async_dispatcher_connect(hass, "test", _add_new_dispatcher)

    async_dispatcher_send(hass, "test", 3)
    async_dispatcher_send(hass, "test", 4)
    async_dispatcher_send(hass, "test", 5)

    assert calls == [3, 4, 4, 5, 5]
