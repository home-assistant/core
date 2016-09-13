"""Tests for async util methods from Python source."""
import asyncio
from asyncio import test_utils

from homeassistant.util import async as hasync


class RunCoroutineThreadsafeTests(test_utils.TestCase):
    """Test case for asyncio.run_coroutine_threadsafe."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.set_event_loop(self.loop)  # Will cleanup properly

    @asyncio.coroutine
    def add(self, a, b, fail=False, cancel=False):
        """Wait 0.05 second and return a + b."""
        yield from asyncio.sleep(0.05, loop=self.loop)
        if fail:
            raise RuntimeError("Fail!")
        if cancel:
            asyncio.tasks.Task.current_task(self.loop).cancel()
            yield
        return a + b

    def target(self, fail=False, cancel=False, timeout=None,
               advance_coro=False):
        """Run add coroutine in the event loop."""
        coro = self.add(1, 2, fail=fail, cancel=cancel)
        future = hasync.run_coroutine_threadsafe(coro, self.loop)
        if advance_coro:
            # this is for test_run_coroutine_threadsafe_task_factory_exception;
            # otherwise it spills errors and breaks **other** unittests, since
            # 'target' is interacting with threads.

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
        future = self.loop.run_in_executor(None, self.target)
        result = self.loop.run_until_complete(future)
        self.assertEqual(result, 3)

    def test_run_coroutine_threadsafe_with_exception(self):
        """Test coroutine submission from a thread to an event loop
        when an exception is raised."""
        future = self.loop.run_in_executor(None, self.target, True)
        with self.assertRaises(RuntimeError) as exc_context:
            self.loop.run_until_complete(future)
        self.assertIn("Fail!", exc_context.exception.args)

    def test_run_coroutine_threadsafe_with_timeout(self):
        """Test coroutine submission from a thread to an event loop
        when a timeout is raised."""
        callback = lambda: self.target(timeout=0)  # noqa
        future = self.loop.run_in_executor(None, callback)
        with self.assertRaises(asyncio.TimeoutError):
            self.loop.run_until_complete(future)
        test_utils.run_briefly(self.loop)
        # Check that there's no pending task (add has been cancelled)
        for task in asyncio.Task.all_tasks(self.loop):
            self.assertTrue(task.done())

    def test_run_coroutine_threadsafe_task_cancelled(self):
        """Test coroutine submission from a tread to an event loop
        when the task is cancelled."""
        callback = lambda: self.target(cancel=True)  # noqa
        future = self.loop.run_in_executor(None, callback)
        with self.assertRaises(asyncio.CancelledError):
            self.loop.run_until_complete(future)
