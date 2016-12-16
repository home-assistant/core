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

    def close(self):
        """Wrap close to handler."""
        self.emit(None)

    def open(self):
        """Wrap open to handler."""
        self._thread.start()
        self.handler.open()

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
        """String name of this."""
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

    def setLevel(self, lvl):
        """Wrap setLevel to handler."""
        return self.handler.setLevel(lvl)

    def setFormatter(self, form):
        """Wrap setFormatter to handler."""
        return self.handler.setFormatter(form)

    def setFilter(self, filt):
        """Wrap setFilter to handler."""
        return self.handler.setFilter(filt)

    def addFilter(self, filt):
        """Wrap addFilter to handler."""
        return self.handler.addFilter(filt)

    def removeFilter(self, filt):
        """Wrap removeFilter to handler."""
        return self.handler.removeFilter(filt)

    def filter(self, record):
        """Wrap filter to handler."""
        return self.handler.filter(record)

    def flush(self):
        """Wrap flush to handler."""
        return self.handler.flush()

    def handle(self, record):
        """Wrap handle to handler."""
        return self.handler.handle(record)

    def handleError(self, record):
        """Wrap handleError to handler."""
        return self.handler.handleError(record)

    def format(self, record):
        """Wrap format to handler."""
        return self.handler.format(record)

    @property
    def level(self):
        """Wrap property level to handler."""
        return self.handler.level

    @property
    def formatter(self):
        """Wrap property formatter to handler."""
        return self.handler.formatter

    def get_name(self):
        """Wrap property set_name to handler."""
        return self.handler.get_name()

    def set_name(self, name):
        """Wrap property get_name to handler."""
        return self.handler.get_name(name)

    name = property(get_name, set_name)
