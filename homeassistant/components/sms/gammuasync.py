"""Async extensions for gammu."""
import asyncio
import logging

import gammu  # pylint: disable=import-error, no-member
import gammu.worker  # pylint: disable=import-error, no-member

_LOGGER = logging.getLogger(__name__)


class GammuAsyncThread(gammu.worker.GammuThread):
    """Thread for phone communication."""

    def __init__(self, queue, config, callback):
        """Initialize thread."""
        gammu.worker.GammuThread.__init__(self, queue, config, callback)

    def _do_command(self, future, cmd, params, percentage=100):
        """Execute single command on phone."""
        func = getattr(self._sm, cmd)
        result = None
        try:
            if params is None:
                result = func()
            elif isinstance(params, dict):
                result = func(**params)
            else:
                result = func(*params)
        except gammu.GSMError as info:
            errcode = info.args[0]["Code"]
            error = gammu.ErrorNumbers[errcode]
            self._callback(future, result, error, percentage)
        except Exception as exception:  # pylint: disable=broad-except
            self._callback(future, None, exception, percentage)
        else:
            self._callback(future, result, None, percentage)


class GammuAsyncWorker(gammu.worker.GammuWorker):
    """Extend gammu worker class for async operations."""

    def worker_callback(self, name, result, error, percents):
        """Execute command from the thread worker."""
        future = None
        if name == "Init" and self._init_future is not None:
            future = self._init_future
        elif name == "Terminate" and self._terminate_future is not None:
            # Set _kill to true on the base class to avoid waiting for termination
            self._thread._kill = True  # pylint: disable=protected-access
            future = self._terminate_future
        elif hasattr(name, "set_result"):
            future = name

        if future is not None:
            if error is None:
                self.loop.call_soon_threadsafe(future.set_result, result)
            else:
                exception = error
                if not isinstance(error, Exception):
                    exception = gammu.GSMError(error)
                self.loop.call_soon_threadsafe(future.set_exception, exception)

    def __init__(self, loop):
        """Initialize the worker class.

        @param callback: See L{GammuThread.__init__} for description.
        """
        gammu.worker.GammuWorker.__init__(self, self.worker_callback)
        self.loop = loop
        self._init_future = None
        self._terminate_future = None
        self._thread = None

    async def init_async(self):
        """Connect to phone."""
        self._init_future = self.loop.create_future()

        self._thread = GammuAsyncThread(self._queue, self._config, self._callback)
        self._thread.start()

        await self._init_future
        self._init_future = None

    async def send_sms_async(self, message):
        """Send sms message via the phone."""
        future = self.loop.create_future()
        self.enqueue(future, commands=[("SendSMS", [message])])
        result = await future
        return result

    async def terminate_async(self):
        """Terminate phone communication."""
        self._terminate_future = self.loop.create_future()
        self.enqueue("Terminate")
        await self._terminate_future

        while self._thread.is_alive():
            await asyncio.sleep(5)
        self._thread = None
