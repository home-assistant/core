"""Logging utilities."""
import asyncio
import logging
import threading

from .async import run_coroutine_threadsafe


class HideSensitiveDataFilter(logging.Filter):
    """Filter API password calls."""

    def __init__(self, text):
        """Initialize sensitive data filter."""
        super().__init__()
        self.text = text

    def filter(self, record):
        """Hide sensitive data in messages."""
        record.msg = record.msg.replace(self.text, '*******')

        return True


# pylint: disable=invalid-name
class AsyncHandler(object):
    """Logging handler wrapper to add a async layer."""

    def __init__(self, loop, handler):
        """Initialize async logging handler wrapper."""
        self.handler = handler
        self.loop = loop
        self._queue = asyncio.Queue(loop=loop)
        self._thread = threading.Thread(target=self._process)

        # Delegate from handler
        self.setLevel = handler.setLevel
        self.setFormatter = handler.setFormatter
        self.addFilter = handler.addFilter
        self.removeFilter = handler.removeFilter
        self.filter = handler.filter
        self.flush = handler.flush
        self.handle = handler.handle
        self.handleError = handler.handleError
        self.format = handler.format

        self._thread.start()

    def close(self):
        """Wrap close to handler."""
        self.emit(None)

    @asyncio.coroutine
    def async_close(self, blocking=False):
        """Close the handler.

        When blocking=True, will wait till closed.
        """
        yield from self._queue.put(None)

        if blocking:
            while self._thread.is_alive():
                yield from asyncio.sleep(0, loop=self.loop)

    def emit(self, record):
        """Process a record."""
        ident = self.loop.__dict__.get("_thread_ident")

        # inside eventloop
        if ident is not None and ident == threading.get_ident():
            self._queue.put_nowait(record)
        # from a thread/executor
        else:
            self.loop.call_soon_threadsafe(self._queue.put_nowait, record)

    def __repr__(self):
        """Return the string names."""
        return str(self.handler)

    def _process(self):
        """Process log in a thread."""
        while True:
            record = run_coroutine_threadsafe(
                self._queue.get(), self.loop).result()

            if record is None:
                self.handler.close()
                return

            self.handler.emit(record)

    def createLock(self):
        """Ignore lock stuff."""
        pass

    def acquire(self):
        """Ignore lock stuff."""
        pass

    def release(self):
        """Ignore lock stuff."""
        pass

    @property
    def level(self):
        """Wrap property level to handler."""
        return self.handler.level

    @property
    def formatter(self):
        """Wrap property formatter to handler."""
        return self.handler.formatter

    @property
    def name(self):
        """Wrap property set_name to handler."""
        return self.handler.get_name()

    @name.setter
    def set_name(self, name):
        """Wrap property get_name to handler."""
        self.handler.name = name
