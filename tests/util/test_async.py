"""Tests for async util methods from Python source."""
import asyncio
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.util import async_ as hasync


@patch("asyncio.coroutines.iscoroutine")
@patch("concurrent.futures.Future")
@patch("threading.get_ident")
def test_fire_coroutine_threadsafe_from_inside_event_loop(
    mock_ident, _, mock_iscoroutine
):
    """Testing calling fire_coroutine_threadsafe from inside an event loop."""
    coro = MagicMock()
    loop = MagicMock()

    loop._thread_ident = None
    mock_ident.return_value = 5
    mock_iscoroutine.return_value = True
    hasync.fire_coroutine_threadsafe(coro, loop)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 5
    mock_ident.return_value = 5
    mock_iscoroutine.return_value = True
    with pytest.raises(RuntimeError):
        hasync.fire_coroutine_threadsafe(coro, loop)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 1
    mock_ident.return_value = 5
    mock_iscoroutine.return_value = False
    with pytest.raises(TypeError):
        hasync.fire_coroutine_threadsafe(coro, loop)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 1
    mock_ident.return_value = 5
    mock_iscoroutine.return_value = True
    hasync.fire_coroutine_threadsafe(coro, loop)
    assert len(loop.call_soon_threadsafe.mock_calls) == 2


@patch("concurrent.futures.Future")
@patch("threading.get_ident")
def test_run_callback_threadsafe_from_inside_event_loop(mock_ident, _):
    """Testing calling run_callback_threadsafe from inside an event loop."""
    callback = MagicMock()
    loop = MagicMock()

    loop._thread_ident = None
    mock_ident.return_value = 5
    hasync.run_callback_threadsafe(loop, callback)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 5
    mock_ident.return_value = 5
    with pytest.raises(RuntimeError):
        hasync.run_callback_threadsafe(loop, callback)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 1
    mock_ident.return_value = 5
    hasync.run_callback_threadsafe(loop, callback)
    assert len(loop.call_soon_threadsafe.mock_calls) == 2


class RunThreadsafeTests(TestCase):
    """Test case for hasync.run_coroutine_threadsafe."""

    def setUp(self):
        """Test setup method."""
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        """Test teardown method."""
        executor = self.loop._default_executor
        if executor is not None:
            executor.shutdown(wait=True)
        self.loop.close()

    @staticmethod
    def run_briefly(loop):
        """Momentarily run a coroutine on the given loop."""

        @asyncio.coroutine
        def once():
            pass

        gen = once()
        t = loop.create_task(gen)
        try:
            loop.run_until_complete(t)
        finally:
            gen.close()

    def add_callback(self, a, b, fail, invalid):
        """Return a + b."""
        if fail:
            raise RuntimeError("Fail!")
        if invalid:
            raise ValueError("Invalid!")
        return a + b

    @asyncio.coroutine
    def add_coroutine(self, a, b, fail, invalid, cancel):
        """Wait 0.05 second and return a + b."""
        yield from asyncio.sleep(0.05, loop=self.loop)
        if cancel:
            asyncio.current_task(self.loop).cancel()
            yield
        return self.add_callback(a, b, fail, invalid)

    def target_callback(self, fail=False, invalid=False):
        """Run add callback in the event loop."""
        future = hasync.run_callback_threadsafe(
            self.loop, self.add_callback, 1, 2, fail, invalid
        )
        try:
            return future.result()
        finally:
            future.done() or future.cancel()

    def target_coroutine(
        self, fail=False, invalid=False, cancel=False, timeout=None, advance_coro=False
    ):
        """Run add coroutine in the event loop."""
        coro = self.add_coroutine(1, 2, fail, invalid, cancel)
        future = hasync.run_coroutine_threadsafe(coro, self.loop)
        if advance_coro:
            # this is for test_run_coroutine_threadsafe_task_factory_exception;
            # otherwise it spills errors and breaks **other** unittests, since
            # 'target_coroutine' is interacting with threads.

            # With this call, `coro` will be advanced, so that
            # CoroWrapper.__del__ won't do anything when asyncio tests run
            # in debug mode.
            self.loop.call_soon_threadsafe(coro.send, None)
        try:
            return future.result(timeout)
        finally:
            future.done() or future.cancel()

    def test_run_callback_threadsafe(self):
        """Test callback submission from a thread to an event loop."""
        future = self.loop.run_in_executor(None, self.target_callback)
        result = self.loop.run_until_complete(future)
        self.assertEqual(result, 3)

    def test_run_callback_threadsafe_with_exception(self):
        """Test callback submission from thread to event loop on exception."""
        future = self.loop.run_in_executor(None, self.target_callback, True)
        with self.assertRaises(RuntimeError) as exc_context:
            self.loop.run_until_complete(future)
        self.assertIn("Fail!", exc_context.exception.args)

    def test_run_callback_threadsafe_with_invalid(self):
        """Test callback submission from thread to event loop on invalid."""
        callback = lambda: self.target_callback(invalid=True)  # noqa: E731
        future = self.loop.run_in_executor(None, callback)
        with self.assertRaises(ValueError) as exc_context:
            self.loop.run_until_complete(future)
        self.assertIn("Invalid!", exc_context.exception.args)


async def test_check_loop_async():
    """Test check_loop detects when called from event loop without integration context."""
    with pytest.raises(RuntimeError):
        hasync.check_loop()


async def test_check_loop_async_integration(caplog):
    """Test check_loop detects when called from event loop from integration context."""
    with patch(
        "homeassistant.util.async_.extract_stack",
        return_value=[
            Mock(
                filename="/home/paulus/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            Mock(
                filename="/home/paulus/homeassistant/components/hue/light.py",
                lineno="23",
                line="self.light.is_on",
            ),
            Mock(
                filename="/home/paulus/aiohue/lights.py",
                lineno="2",
                line="something()",
            ),
        ],
    ):
        hasync.check_loop()
    assert (
        "Detected I/O inside the event loop. This is causing stability issues. Please report issue for hue doing I/O at homeassistant/components/hue/light.py, line 23: self.light.is_on"
        in caplog.text
    )


async def test_check_loop_async_custom(caplog):
    """Test check_loop detects when called from event loop with custom component context."""
    with patch(
        "homeassistant.util.async_.extract_stack",
        return_value=[
            Mock(
                filename="/home/paulus/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            Mock(
                filename="/home/paulus/config/custom_components/hue/light.py",
                lineno="23",
                line="self.light.is_on",
            ),
            Mock(
                filename="/home/paulus/aiohue/lights.py",
                lineno="2",
                line="something()",
            ),
        ],
    ):
        hasync.check_loop()
    assert (
        "Detected I/O inside the event loop. This is causing stability issues. Please report issue to the custom component author for hue doing I/O at custom_components/hue/light.py, line 23: self.light.is_on"
        in caplog.text
    )


def test_check_loop_sync(caplog):
    """Test check_loop does nothing when called from thread."""
    hasync.check_loop()
    assert "Detected I/O inside the event loop" not in caplog.text


def test_protect_loop_sync():
    """Test protect_loop calls check_loop."""
    calls = []
    with patch("homeassistant.util.async_.check_loop") as mock_loop:
        hasync.protect_loop(calls.append)(1)
    assert len(mock_loop.mock_calls) == 1
    assert calls == [1]
