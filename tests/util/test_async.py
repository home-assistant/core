"""Tests for async util methods from Python source."""
import asyncio
from asyncio import test_utils
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.util import async as hasync


@patch('asyncio.coroutines.iscoroutine')
@patch('concurrent.futures.Future')
@patch('threading.get_ident')
def test_run_coroutine_threadsafe_from_inside_event_loop(
        mock_ident, _, mock_iscoroutine):
    """Testing calling run_coroutine_threadsafe from inside an event loop."""
    coro = MagicMock()
    loop = MagicMock()

    loop._thread_ident = None
    mock_ident.return_value = 5
    mock_iscoroutine.return_value = True
    hasync.run_coroutine_threadsafe(coro, loop)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 5
    mock_ident.return_value = 5
    mock_iscoroutine.return_value = True
    with pytest.raises(RuntimeError):
        hasync.run_coroutine_threadsafe(coro, loop)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 1
    mock_ident.return_value = 5
    mock_iscoroutine.return_value = False
    with pytest.raises(TypeError):
        hasync.run_coroutine_threadsafe(coro, loop)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 1
    mock_ident.return_value = 5
    mock_iscoroutine.return_value = True
    hasync.run_coroutine_threadsafe(coro, loop)
    assert len(loop.call_soon_threadsafe.mock_calls) == 2


@patch('asyncio.coroutines.iscoroutine')
@patch('concurrent.futures.Future')
@patch('threading.get_ident')
def test_fire_coroutine_threadsafe_from_inside_event_loop(
        mock_ident, _, mock_iscoroutine):
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


@patch('concurrent.futures.Future')
@patch('threading.get_ident')
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


class RunThreadsafeTests(test_utils.TestCase):
    """Test case for asyncio.run_coroutine_threadsafe."""

    def setUp(self):
        """Test setup method."""
        super().setUp()
        self.loop = asyncio.new_event_loop()
        self.set_event_loop(self.loop)  # Will cleanup properly

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
            asyncio.tasks.Task.current_task(self.loop).cancel()
            yield
        return self.add_callback(a, b, fail, invalid)

    def target_callback(self, fail=False, invalid=False):
        """Run add callback in the event loop."""
        future = hasync.run_callback_threadsafe(
            self.loop, self.add_callback, 1, 2, fail, invalid)
        try:
            return future.result()
        finally:
            future.done() or future.cancel()

    def target_coroutine(self, fail=False, invalid=False, cancel=False,
                         timeout=None, advance_coro=False):
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

    def test_run_coroutine_threadsafe(self):
        """Test coroutine submission from a thread to an event loop."""
        future = self.loop.run_in_executor(None, self.target_coroutine)
        result = self.loop.run_until_complete(future)
        self.assertEqual(result, 3)

    def test_run_coroutine_threadsafe_with_exception(self):
        """Test coroutine submission from thread to event loop on exception."""
        future = self.loop.run_in_executor(None, self.target_coroutine, True)
        with self.assertRaises(RuntimeError) as exc_context:
            self.loop.run_until_complete(future)
        self.assertIn("Fail!", exc_context.exception.args)

    def test_run_coroutine_threadsafe_with_invalid(self):
        """Test coroutine submission from thread to event loop on invalid."""
        callback = lambda: self.target_coroutine(invalid=True)  # noqa
        future = self.loop.run_in_executor(None, callback)
        with self.assertRaises(ValueError) as exc_context:
            self.loop.run_until_complete(future)
        self.assertIn("Invalid!", exc_context.exception.args)

    def test_run_coroutine_threadsafe_with_timeout(self):
        """Test coroutine submission from thread to event loop on timeout."""
        callback = lambda: self.target_coroutine(timeout=0)  # noqa
        future = self.loop.run_in_executor(None, callback)
        with self.assertRaises(asyncio.TimeoutError):
            self.loop.run_until_complete(future)
        test_utils.run_briefly(self.loop)
        # Check that there's no pending task (add has been cancelled)
        for task in asyncio.Task.all_tasks(self.loop):
            self.assertTrue(task.done())

    def test_run_coroutine_threadsafe_task_cancelled(self):
        """Test coroutine submission from tread to event loop on cancel."""
        callback = lambda: self.target_coroutine(cancel=True)  # noqa
        future = self.loop.run_in_executor(None, callback)
        with self.assertRaises(asyncio.CancelledError):
            self.loop.run_until_complete(future)

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
        callback = lambda: self.target_callback(invalid=True)  # noqa
        future = self.loop.run_in_executor(None, callback)
        with self.assertRaises(ValueError) as exc_context:
            self.loop.run_until_complete(future)
        self.assertIn("Invalid!", exc_context.exception.args)
